# Pico Launcher CN 0.1.1 · 文件名显示测试版

基于 LNH team 官方 Pico Launcher 的中文显示派生版本。游戏列表和上屏标题直接显示 SD 卡上的真实文件名；中文、版本号、汉化组、括号和扩展名按原样保留，游戏图标、动画图标和封面继续使用。

## 直接使用

本地构建后的程序位于 `releases/0.1.1-filename-test/_picoboot.nds`，不需要解压。发布时提供同名独立附件；源码仓库不保存生成的程序。

1. 把 SD 卡根目录现有的 `_picoboot.nds` 复制到电脑留作备份。
2. 将上面的程序文件直接复制到 SD 卡根目录，覆盖同名文件。
3. 保留已有 `_pico` 文件夹和 Pico Loader 文件，再启动 DS Pico。

较长的列表名称在选中后会滚动；上屏底部也保留完整文件名滚动显示。需要回退时使用自己的备份；本地保留了上一版的，也可使用 `releases/0.1.0-banner-test/_picoboot.nds`。

这些 `.nds` 文件是选游戏菜单，不是卡带的 `.uf2` 固件。程序会在 [Releases](https://github.com/pangqichenmmm/pico-launcher-cn/releases) 中作为独立附件提供；以实际存在的附件为准，不要求使用者解压安装包。

本 fork 的中文显示开发分支为 `chinese-filename`，`develop` 保留上游基线。当前是测试版本，真机验证范围见下文。

## 项目目录

| 目录 | 用途 |
|---|---|
| `releases/` | 本地可直接复制的最新版、回退版本及校验记录，不随源码提交 |
| `arm7/`、`arm9/`、`common/` | 菜单源码和运行资源 |
| `_pico/` | 上游自带主题资源 |
| `libs/libtwl/` | 固定版本的上游 Git 子模块 |
| `fonts/` | 中文字体声明、OFL 许可与生成记录 |
| `tools/`、`tests/` | 可重新构建、验证字体及文字显示的脚本和测试 |
| `docs/` | 使用说明、测试记录和显示预览 |

编译器副本、下载缓存、编译中间文件和本地交付目录均不随源码提交。需要重新编译时，脚本会在项目内准备工具；已经生成的两套中文字体保留在源码中。

## 功能和验证范围

- 两套共享中文补充字库覆盖 GB2312 的 6,763 个汉字及相关符号，共 7,447 个字符，原有西文、日文假名字形及四种字号保留。
- 标题来源固定为文件名。主标题缓冲区支持最长 255 个 BMP 字符的文件名，Material 和自定义主题均已调整。
- 字体新增约 0.965 MiB。菜单文件为 1,502,720 字节，对照原版构建为 491,008 字节。
- 已通过电脑上的编译、字体覆盖、UTF-8 文件名、2D／3D 像素一致性、裁切、省略显示和 CRC 检查。
- 0.1.0 收到用户“可以正常看到 banner 中文”的反馈；0.1.1 的文件名显示行为仍待真机确认。NDS／Lite、DSi 和 3DS／2DS 均为兼容目标，不能据此宣称全部机型已实测。
- 字库以常用简体字为主，不涵盖全部繁体字、生僻字、扩展汉字或 emoji。设置和提示沿用原版语言。

详情见 [测试记录](docs/TESTING-CN.md) 和 [实际文字绘制预览](docs/previews/Filename-render-preview.png)，预览不是主机截图。

## 构建

Windows 需要 Python 3.11 或以上，以及带 Bash 的 Git for Windows。构建路径应避免空格；编译器仅准备在项目内的 `.tools/`，不需要安装 WSL 或 Docker。

```powershell
python tools/bootstrap_windows.py
python tools/build_windows.py
```

成功后生成 `LAUNCHER.nds`。编译工具的 URL 和 SHA256 已锁定在 `tools/toolchain-windows.lock.json`。本地验证和本 fork 的自动构建均使用 BlocksDS 1.24.0 与 ARM GCC 16.2。自动构建在 Windows 2022 上执行 C++ 绘制测试、字体和二进制校验，结果见 [Actions](https://github.com/pangqichenmmm/pico-launcher-cn/actions)。

在已配置 BlocksDS 的 Linux 环境中，先初始化子模块，然后可直接运行 `make`。

验证前安装 Python 依赖：

```powershell
python -m pip install -r tools/requirements-fonts.txt
```

如要修改字库或重新生成预览，还需要下载字体源文件：

```powershell
python tools/fetch_build_inputs.py
python tools/build_chinese_fonts.py
```

## 验证与准备程序文件

C++ 文字绘制测试需要本机已安装 Visual Studio C++ 编译器。程序校验和字体覆盖检查使用 Pillow、fontTools。

```powershell
python tools/test_windows.py
python tools/verify_and_preview.py
python tools/package_cn.py
```

最后一个命令将程序放入对应 `releases/` 目录，并准备安装说明、许可和校验值，不创建 ZIP。没有字体源文件或临时绘制输出时，验证命令仍会执行核心检查，并保留 `docs/previews/` 中已有的预览。

Release 工作流只会在手动发布发行版后执行：先重新构建和验证，再逐个附加 `_picoboot.nds`、校验值、说明和许可。GitHub 自动提供的源码归档及 Actions 构建归档不属于安装包。

可用 `--black2-rom "游戏路径"` 为测试命令提供用户自己的日版《黑2》（IREJ）汉化 ROM。测试只读访问它，提取数据留在被忽略的 `.cache/` 中，清理时可以删除。

## 来源与许可

- 官方基线：[LNH-team/pico-launcher](https://github.com/LNH-team/pico-launcher)，提交 `dc64a34cabe26a9ac12d5592ada2d729cdfc6328`，原 zlib 许可保留在 `LICENSE.txt`。
- libtwl 固定提交：`aa3b2a23c10185a10449ffa685bb7933d5d5a784`。
- 参考 [chaye7417 的中文增强版](https://github.com/chaye7417/pico-launcher/tree/chinese) 的思路，中文补充机制和转换脚本单独实现。
- 新字形来自 Noto Sans CJK SC Regular，修改后命名为 PicoCN；Adobe 版权声明和 SIL OFL 1.1 保留在 `fonts/`。字体与程序代码各按其许可分发。
- 其余组件声明保留在 `licenses/`。本项目不包含游戏 ROM、WRFU Tester ROM、BIOS 或卡带硬件固件。
