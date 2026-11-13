# Data Review

用于人工筛选 CAD Agent 轨迹的本地网页：左侧查看对话、思考来源、工具调用和返回，右侧对照 Target / Rebuild 等测图；点击 **✅ / ❌** 保存后，自动跳到下一条未标注记录。

这是从 `step-8B-sft/sites/v63-trajectory-labeler` 独立发布的代码。原始轨迹、STEP、模型代码和既有人工标注仍留在原数据目录；本仓库不包含实际数据集或用户标签。项目导航见 [cad-mind](https://github.com/Yulia2233/cad-mind)。

## 运行示例

查看网页只需 Python 3.10+，无需模型/API key，无需安装 CAD SDK：

```bash
git clone https://github.com/Yulia2233/data-review.git
cd data-review
python3 server.py --root . --catalog examples/catalog.json \
  --data-dir .runtime/demo --images examples/images --port 8778
```

打开 `http://127.0.0.1:8778/`。示例轨迹明确标为合成演示，不是实际 Agent 运行；示例 box 的 STEP 与等测图由 SimpleCADAPI 2.2.7 生成。测试标注只写 `.runtime/demo/annotations/`。

## 连接既有批注数据

先备份 `marks.json` 和 `history.jsonl`，停止自己原来的批注服务或选用不同端口，然后从本仓库运行：

```bash
python3 server.py \
  --root /path/to/step-8B-sft \
  --data-dir /path/to/step-8B-sft/sites/v63-trajectory-labeler \
  --catalog /path/to/step-8B-sft/sites/v63-trajectory-labeler/active-catalog.json \
  --images /path/to/step-8B-sft/sites/v63-trajectory-labeler/images \
  --annotations /path/to/step-8B-sft/sites/v63-trajectory-labeler/annotations \
  --port 8778
```

保持 catalog 的 `case` 标识和 annotations 路径不变，即可沿用原标签，无须复制或重建它们。不要让两个服务器同时写同一个 annotations 目录。发布代码不会自动改变当前活动批次，也不会自动将新生成轨迹加入旧 catalog。

## 功能与边界

- 按批次、标签和名称筛选；上一件/下一件，保存失败留在当前件。
- 显示 CAD Code `cad-code-session-v2` 原始顺序、工具参数/返回/错误和内联工具图片；原始 JSON 可下载。不会执行轨迹里的代码或命令。
- 支持已转换的 Qwen 轨迹；保留 `reasoning_content` 和来源标识，事后补写解释单独标注。接口未返回的思考保持空段。
- 标签保存为 `pass` / `fail`，当前标签原子替换，变更历史追加到 `history.jsonl`。不会因切换 catalog 删除旧标签。
- 原始 Target / Rebuild / notebook 只读；缺少重建如实显示。模型说明取自原报告/catalog，不是网页自动生成。
- 渲染为独立的可选步骤：读取 STEP，采用相同等测相机、并行投影和联合包围盒；SDK 回退到分别适配时页面注明。记录源 STEP hash；不会运行历史 notebook 补造 rebuild。
- 仅监听 `127.0.0.1`，沿用 Host / Origin / 页面 token 检查。本地可信 catalog 指定可读文件；不要把不可信 catalog 当作权限边界或把服务直接公开到互联网。
- 人工 ✅ 是审核意见，不等于独立几何验收或训练集收录。正式收录仍由批量工程的数据打包/来源核对脚本完成。

## 文档与源码

| 入口 | 用途 |
| --- | --- |
| [docs/usage.md](docs/usage.md) | 配置、渲染、标签备份与迁移 |
| [docs/catalog.md](docs/catalog.md) | catalog、轨迹、图片和标签格式 |
| [docs/legacy-history.md](docs/legacy-history.md) | 原站历史说明；批次数量是历史快照，不是当前状态 |
| `server.py` / `app.js` / `index.html` / `styles.css` | 本地 API 与原批注界面 |
| `qwen_adapter.py` | Qwen 消息到显示结构的适配 |
| `render_pairs.py` / `render_rerun934.py` | 可选离线等测图渲染 |
| `build_catalog.py` / `add_*_catalog.py` | 原工程历史批次导入脚本，依赖其目录和固定清单，详见文档 |

## 验证

```bash
python3 -m unittest discover -s tests -v
node --check app.js
```

测试使用临时数据和独立随机端口，核对原始 JSON/媒体保留、两种标注、追加历史、重启持久性和原有来源拒绝检查；不读取或写入正式标签，不调用模型 API。
