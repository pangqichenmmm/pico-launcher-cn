#pragma once
#include "ndsBanner.h"

inline const char16_t* nds_getBannerTitleStart(const char16_t* title)
{
    for (int i = 0; i < 128; ++i)
    {
        const char16_t c = title[i];
        if (c == 0)
            return nullptr;
        if (c != u' ' && c != u'\t' && c != u'\r' && c != u'\n' && c != u'\u3000' && c != u'\uFEFF')
            return title + i;
    }
    return nullptr;
}

inline const char16_t* nds_getPreferredBannerTitle(const nds_banner_t& banner)
{
    if (banner.header.version >= NDS_BANNER_VERSION_2)
    {
        const auto* title = nds_getBannerTitleStart(banner.title[NDS_BANNER_TITLE_LANGUAGE_CHINESE]);
        if (title)
            return title;
    }

    constexpr int languages[] = {
        NDS_BANNER_TITLE_LANGUAGE_ENGLISH, NDS_BANNER_TITLE_LANGUAGE_JAPANESE,
        NDS_BANNER_TITLE_LANGUAGE_FRENCH, NDS_BANNER_TITLE_LANGUAGE_GERMAN,
        NDS_BANNER_TITLE_LANGUAGE_ITALIAN, NDS_BANNER_TITLE_LANGUAGE_SPANISH,
        NDS_BANNER_TITLE_LANGUAGE_KOREAN
    };
    for (int language : languages)
    {
        if (language == NDS_BANNER_TITLE_LANGUAGE_KOREAN && banner.header.version < NDS_BANNER_VERSION_3)
            continue;
        const auto* title = nds_getBannerTitleStart(banner.title[language]);
        if (title)
            return title;
    }
    return nullptr;
}
