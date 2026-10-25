#include "common.h"
#include "gui/font/nitroFont2.h"
#include "romBrowser/FileType/Nds/ndsBannerTitle.h"
#include "core/StringUtil.h"
#include <algorithm>
#include <array>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
}

struct Font
{
    std::vector<u8> data;
    nft2_header_t header{};

    explicit Font(const std::filesystem::path& path)
    {
        std::ifstream stream(path, std::ios::binary);
        require(stream.good(), "Cannot open test font asset");
        data.assign(std::istreambuf_iterator<char>(stream), {});
        require(data.size() >= 20, "Truncated font header");
        auto read32 = [this](size_t offset) {
            u32 value;
            std::memcpy(&value, data.data() + offset, sizeof(value));
            return value;
        };
        header.signature = read32(0);
        header.glyphInfoPtr = reinterpret_cast<const nft2_glyph_t*>(data.data() + read32(4));
        header.charMapPtr = reinterpret_cast<const nft2_char_map_entry_t*>(data.data() + read32(8));
        header.glyphDataPtr = data.data() + read32(12);
        header.ascend = data[16];
        header.descend = data[17];
        std::memcpy(&header.glyphCount, data.data() + 18, 2);
    }
};

static void test_title_selection()
{
    nds_banner_t banner{};
    banner.header.version = NDS_BANNER_VERSION_103;
    std::u16string english = u"Pokemon Black 2\nNintendo";
    std::copy(english.begin(), english.end(), banner.title[1]);
    std::u16string chinese = u"\n精灵宝可梦 黑2\nNintendo\n";
    std::copy(chinese.begin(), chinese.end(), banner.title[6]);
    require(std::u16string(nds_getPreferredBannerTitle(banner)) == chinese.substr(1),
            "Chinese title must be preferred and leading blank line removed");
    std::fill(std::begin(banner.title[6]), std::end(banner.title[6]), u' ');
    require(nds_getPreferredBannerTitle(banner) == banner.title[1],
            "A whitespace-only Chinese slot must fall back to English");
    std::copy(chinese.begin(), chinese.end(), banner.title[6]);
    banner.header.version = NDS_BANNER_VERSION_1;
    require(nds_getPreferredBannerTitle(banner) == banner.title[1],
            "DS v1 banners must not use the Chinese extension slot");
    std::fill(std::begin(banner.title[1]), std::end(banner.title[1]), 0);
    banner.title[0][0] = u'ポ';
    require(nds_getPreferredBannerTitle(banner) == banner.title[0],
            "Japanese title fallback must be preserved");
    banner.title[0][0] = 0;
    require(nds_getPreferredBannerTitle(banner) == nullptr,
            "An empty banner must have no title");
}

static void test_filename_decoding()
{
    char16_t decoded[256];
    StringUtil::Copy(decoded, "口袋妖怪(精灵宝可梦) 黑2(官译V5).nds", 256);
    require(std::u16string(decoded) == u"口袋妖怪(精灵宝可梦) 黑2(官译V5).nds",
            "UTF-8 Chinese filenames must decode to the right characters");
    StringUtil::Copy(decoded, "口袋妖怪精灵宝可梦.nds", 5);
    require(std::u16string(decoded) == u"口袋妖怪",
            "Truncating a filename must preserve complete UTF-16 characters");
}

static void check_guards(const std::vector<u8>& bytes)
{
    require(std::all_of(bytes.begin(), bytes.begin() + 64, [](u8 b) { return b == 0xAB; }),
            "Renderer wrote before the output buffer");
    require(std::all_of(bytes.end() - 64, bytes.end(), [](u8 b) { return b == 0xAB; }),
            "Renderer wrote after the output buffer");
}

static void test_render(const nft2_header_t* font, int x, int y)
{
    constexpr u32 width = 96, height = 32;
    std::vector<u8> tiled(64 + width * height / 2 + 64, 0xAB);
    std::vector<u8> alpha(64 + width * height + 64, 0xAB);
    std::fill(tiled.begin() + 64, tiled.end() - 64, 0);
    std::fill(alpha.begin() + 64, alpha.end() - 64, 0);
    nft2_string_render_params_t params{};
    params.x = x; params.y = y; params.width = width - 7; params.height = height;
    params.a5i3 = false; params.onlyRenderWholeGlyphs = false;
    const char16_t* text = u"精灵宝可梦 黑2\n中文文件名.nds";
    nft2_renderString(font, text, tiled.data() + 64, width, &params);
    params.a5i3 = true;
    nft2_renderString(font, text, alpha.data() + 64, width, &params);
    check_guards(tiled); check_guards(alpha);
    bool visible = false;
    for (u32 py = 0; py < height; ++py)
    {
        for (u32 px = 0; px < width; ++px)
        {
            u32 tile = (py / 16) * (width / 32) * 8 + (px / 32) * 8
                     + ((py % 16) / 8) * 4 + ((px % 32) / 8);
            u32 pixel = tile * 64 + (py % 8) * 8 + px % 8;
            u8 actual = (tiled[64 + pixel / 2] >> ((pixel % 2) * 4)) & 15;
            u8 expected = alpha[64 + py * width + px] >> 4;
            require(actual == expected, "2D and 3D text rasterization disagree");
            visible = visible || actual != 0;
        }
    }
    require(visible, "Chinese text rendered no visible pixels");
}

static void export_preview(const nft2_header_t* font, const std::filesystem::path& output,
                           const char16_t* text, u32 viewportWidth = 244)
{
    constexpr u32 width = 256, height = 16;
    std::array<u8, width * height> pixels{};
    nft2_string_render_params_t params{};
    params.width = viewportWidth; params.height = height; params.a5i3 = true;
    nft2_renderStringEllipsis(font, text, pixels.data(), width, &params, u" ... ");
    std::ofstream stream(output, std::ios::binary);
    stream << "P5\n256 16\n255\n";
    for (u8 pixel : pixels)
        stream.put(static_cast<char>(255 - (pixel >> 4) * 17));
}

int main(int argc, char* argv[])
{
    try
    {
        require(argc == 2 || argc == 3, "Expected the repository path and optional Black 2 banner");
        const std::filesystem::path assets = std::filesystem::path(argv[1]) / "arm9/data";
        Font small(assets / "PicoCN-Small.nft2");
        Font regular(assets / "PicoCN-Regular.nft2");
        nft2_setFallbackFonts(&small.header, &regular.header);
        const auto previewFolder = std::filesystem::path(argv[1]) / ".cache/host-tests/renders";
        std::filesystem::create_directories(previewFolder);
        for (const char* name : {"NotoSansJP-Regular-10.nft2", "NotoSansJP-Medium-10.nft2",
                                 "NotoSansJP-Medium-11.nft2", "NotoSansJP-Medium-7_5.nft2"})
        {
            Font base(assets / name);
            u32 width, height;
            nft2_measureString(&base.header, u"精灵宝可梦 黑2", width, height);
            require(width >= 7 * 8, "Chinese fallback advances were not measured");
            test_render(&base.header, 0, 0);
            test_render(&base.header, -5, -3);
            std::array<u8, 128 * 16> output{};
            nft2_string_render_params_t params{};
            params.width = 72; params.height = 16; params.a5i3 = true;
            nft2_renderStringEllipsis(&base.header,
                u"口袋妖怪精灵宝可梦黑2全文本官译测试长文件名", output.data(), 128, &params, u" ... ");
            require(params.textWidth <= 72, "Ellipsis text exceeds its display width");
            export_preview(&base.header, previewFolder / (std::string(name) + ".pgm"),
                           u"精灵宝可梦 黑2 / Pokémon Black 2");
        }
        Font filenameFont(assets / "NotoSansJP-Medium-7_5.nft2");
        export_preview(&filenameFont.header, previewFolder / "filename.pgm",
                       u"口袋妖怪(精灵宝可梦) 黑2(V5+DSi增强AP+全文本官译V5)(JP)(ACG汉化组+口袋群星SP+天涯+Desaix)(4096Mb).nds");
        Font listFont(assets / "NotoSansJP-Medium-10.nft2");
        export_preview(&listFont.header, previewFolder / "goldensun-banner.pgm",
                       u"おうごんのたいよう", 152);
        export_preview(&listFont.header, previewFolder / "goldensun-filename.pgm",
                       u"黄金太阳 漆黑的黎明 1.1(JP)(ACG汉化组)(-2048Mb).nds", 152);
        export_preview(&filenameFont.header, previewFolder / "goldensun-filename-small.pgm",
                       u"黄金太阳 漆黑的黎明 1.1(JP)(ACG汉化组)(-2048Mb).nds", 220);
        test_title_selection();
        test_filename_decoding();
        if (argc == 3)
        {
            nds_banner_t banner{};
            std::ifstream stream(argv[2], std::ios::binary);
            stream.read(reinterpret_cast<char*>(&banner), sizeof(banner));
            require(stream.gcount() == sizeof(banner), "Incomplete real-ROM banner fixture");
            const auto* title = nds_getPreferredBannerTitle(banner);
            require(title && std::u16string(title).starts_with(u"精灵宝可梦 黑2\nNintendo"),
                    "The user's real Black 2 banner selected the wrong title");
            std::cout << "PASS: actual Black 2 ROM banner title\n";
        }
        std::cout << "PASS: four font styles, Chinese fallback, 2D/3D pixels, clipping, ellipsis, banner selection, UTF-8 filenames\n";
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
