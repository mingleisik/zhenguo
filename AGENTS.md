# 真果鉴开发约定

## 项目目标

构建 Flutter 独立应用。本线以桌面端为主维护线：Windows 10+ x64 与 Linux x64（Ubuntu 26.04）。站源请求、解析、在线播放及后续下载均在设备端完成；成品不依赖旧短剧库程序、旧项目路径或远程自建服务。可以迁移已经验证的业务逻辑，并将依赖一并纳入本项目。Android 手机与 Android TV 源码保留，跟随上游作者节奏，不在本线主动推进。

## 优先级与交付

1. Windows 10+ x64 桌面端为第一优先级：`windows/` 平台工程、`scripts/build_windows.py`、CI `windows` 任务与 `dist/windows` 便携包。构建需 Windows、MinGW-w64（`x86_64-w64-mingw32-gcc`）和 Visual Studio 生成工具。
2. Linux x64（Ubuntu 26.04）桌面端第二优先级：`linux/` 平台工程、`scripts/build_linux.py`、CI `linux` 任务与 `dist/linux` deb 安装包。CI 必须显式固定 `ubuntu-26.04`，不要用 `ubuntu-latest`（它目前仍是 24.04，会在 2026 年 10 月 19 日至 11 月 19 日之间切到 26.04）。构建需 clang、CMake、Ninja、`libgtk-3-dev`、`liblzma-dev`、`libmpv-dev`、`libepoxy-dev`、`build-essential` 和 `dpkg-dev`；deb 里的原生库按 26.04 的 glibc 与 GTK3 编译，只保证在 26.04 上运行。
3. Android 手机与 Android TV 源码保留、跟随上游节奏，不在本线主动推进（含安卓 6 兼容：minSdk 23；FFmpegKit 及合并、导出、封面解码功能已按 2026-10-02 要求彻底移除，离线播放走 Go 核心不受影响）。iOS 端仍不维护；macOS 端停止编译，平台源码保留但不参与 CI 构建与发布产物。
4. 首版优先完成可用的在线播放闭环：浏览、搜索、剧集详情、选集、播放、错误重试。
5. 其他功能按 README.md 中的待办顺序逐项实现，完成后更新状态。不要为了未到优先级的功能推迟首版。

## 桌面端平台约定

- 红果鉴与真果鉴共用同一份平台源码：`--all-sources` 切换版本，`build_linux.py` 额外导出 `DUANJU_EDITION`，由 `linux/CMakeLists.txt` 生成 GTK 应用标识与窗口标题，同一份源码可直接产出两个 deb。
- Go 核心产物位置固定：`windows/runner/duanju_core.dll` 与 `linux/runner/libduanju_core.so`，均由平台 CMake 装到可执行文件同级的库目录，Dart 侧按可执行文件位置加载。
- Linux 打包只用系统 `dpkg-deb` / `dpkg-shlibdeps`；`libmpv` 由 `media_kit_video` 在构建期链接，`Depends` 里必须保留 libmpv，缺失时由 `scripts/linux_package.py` 手工补上。
- `media_kit_libs_linux` 会在 CMake 配置阶段从 github.com 下载并编译 mimalloc，构建机必须能直连 github.com；国内网络需要代理。
- 本机没有 Linux 工具链，也不允许调用 WSL，Linux 产物只能由 GitHub Actions 的 `ubuntu-26.04` 任务产出；本地只能验证 Go 交叉编译、Dart 静态检查与打包脚本单测。

## 实施与验证

按用户 2026-09-21 的要求，目前完成功能优先，暂停测试与回归，待用户安排后集中执行。源码格式整理及任务收尾同步仍执行；未验证的实现明确标为开发快照，不作为通过验收的版本。

恢复集中验证后，先完整实现当前交付范围，再集中执行静态检查、构建、自动化和设备验证；不要每改一个小功能就测试。集中验证发现问题后，修复并执行相关复验。未验证的平台和行为必须明确标注，不得将生成源码等同于可用成品。

直接在本项目中维护源码。临时目录仅放工具、构建缓存和验证产物，不在临时目录维护另一份正式实现。不要修改旧短剧库和果果剧库。

## 任务收尾同步

每次完成开发、修复或文档修改后，在必要检查通过、最终回复之前，必须执行 `python3 scripts/finish_task.py --message "本次实际完成的变更"`。脚本只将干净源码同步到本项目同级的 `../guoapp`，并生成 `真果·鉴-YYYYMMDDHHMM.zip` 纯源码压缩包；不要求目标存在 `.git`，不执行提交、tag、分支、推送或其他 Git 操作。同一分钟内重复执行会追加序号，不覆盖已有压缩包，作为可恢复的版本。有后续修改时重新执行收尾，并用 `python3 scripts/sync_source.py --check` 确认一致；失败先处理原因，不要声称已完成。

`guoapp` 是面向 GitHub 的纯源码镜像，不依赖本地 Git 仓库；其余文件与导出源码保持一致，包含源码、必要资源、构建配置、锁文件、测试和 Actions，排除 SDK、第三方依赖目录、缓存、编译产物、签名文件和个人配置。目标目录若已有 `.git`，同步时原样保留但不读取、不修改、不删除。新增源码根目录或构建输入时同步维护脚本的收录规则。

功能版本递增 `pubspec.yaml` 的版本号和构建号。源码恢复以版本号、源码压缩包和 README 记录为依据；未通过检查的代码不得标为已完成版本。

如果正在 `guoapp` 本身工作，不向自身同步；脚本会跳过此情况。不要为了同步另建临时源码副本。

## 代码与资料

保持单一 README.md 使用说明，并在其中维护优先级待办与平台验证状态；不要创建零散 docs 文档。AGENTS.md 仅记录开发约定。

不新增解释性代码注释，必要的编译或工具指令除外。采用清晰命名和模块边界。不要提交密钥、个人配置、下载的视频、SDK 或构建缓存。

不要查看、下载、分析或处理站源图片。页面可正常显示海报地址；开发验证使用合成数据或拦截图片请求。用户直接提供的界面截图可以查看。

遵守先实现后集中验证的节奏；未经用户明确要求，不启动子 AGENT。
