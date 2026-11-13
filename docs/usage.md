# 使用与迁移

## 路径

| CLI / 环境变量 | 含义 | 默认值 |
| --- | --- | --- |
| `--root` / `DATA_REVIEW_ROOT` | catalog 内相对产物路径的根目录 | 独立仓库目录 |
| `--data-dir` / `DATA_REVIEW_DATA_DIR` | catalog、渲染状态和默认本地输出 | 独立仓库目录 |
| `--catalog` / `DATA_REVIEW_CATALOG` | 要显示的固定 catalog | data-dir 的 `active-catalog.json`，无则 `catalog.json` |
| `--images` / `DATA_REVIEW_IMAGES` | `case/target.png`、`rebuild.png`、`render.json` | data-dir 的 `images/` |
| `--annotations` / `DATA_REVIEW_ANNOTATIONS` | `marks.json` 与 `history.jsonl` | data-dir 的 `annotations/` |
| `--port` | 本机 HTTP 端口 | 8778 |

CLI 优先于相应环境变量。显式指定不存在的 `--catalog` 会报错。空仓库不指定 catalog 时可显示空列表；旧工程没有 catalog 时仍支持 `datasets/data-traj2/stepir-v6.3` 和 `stepir_geom_gen/cadcode_synth_v63` 的历史回退加载。网页不自动扫描所有批次。

## 渲染

可选，要求 Python 3.12/3.13 和 SimpleCADAPI 2.2.7。查看已有图片不需要安装它。请在独立环境安装：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple -r requirements-render.txt
export DATA_REVIEW_ROOT=/path/to/artifact-root
export DATA_REVIEW_DATA_DIR=/path/to/local-review-state
export DATA_REVIEW_CATALOG=/path/to/catalog.json
.venv/bin/python render_pairs.py --scope all --workers 3
```

渲染输出固定写 `DATA_REVIEW_DATA_DIR/images/`；启动 viewer 时让 `--images` 指向这个目录。`--case CASE_ID`、`--limit N`、`--timeout 300` 可缩小重试范围。独立子进程有超时，每件 meta 记录 hash、相机和错误。SDK 的无效 BREP/多根回退会标 `camera.fit=independent`，并不伪称同尺度。旧 `render_rerun934.py --batch rerun934` 可按已有批次标识渲染；历史 datav1 原样本没有 rebuild，按原记录显示缺失。

## 标签和批次

catalog 的 `case` 是标签的唯一键。同零件新会话应使用新键，例如 `rerun934--part-name`；不能仅靠文件名混用历史标签。切换 catalog 不会删除 marks 里暂时不显示的键。迁移前在服务停止写入时备份整个 annotations 目录；不要只拷贝当前显示批次的键。

`build_catalog.py` 固定构建历史 1572 快照，`add_datav1_catalog.py` 固定核对 1772 和旧标签数量，`add_rerun934_catalog.py` 固定核对 934，`add_datav1_v63_catalog.py` 固定核对 565。这些是原工程的可追溯导入脚本，不是任意数据集通用发现器；只在匹配的原工程快照上运行。通过 `DATA_REVIEW_ROOT` 指向原工程、`DATA_REVIEW_DATA_DIR` 指向本地状态；执行前阅读脚本并备份。不要在正在批注时重建目录。

正式数据收录由 `step-8B-sft/work/tools_extra/` 的原打包脚本完成。网页本身不会复制 ✅ 到 `formal-data-traj`、删除 ❌ 或修改原始轨迹。
