# STEPIR v6.3 轨迹标注

独立本地审核网页。左侧按 CAD Code 导出消息顺序展示正文、任务输入、工具参数、工具返回和错误；右侧为 Target / Rebuild 的同尺度等测图。只有 ✅ / ❌ 两种标注，保存成功后自动切换下一件未标注零件。

```bash
python3 sites/v63-trajectory-labeler/server.py --port 8778
```

打开 <http://127.0.0.1:8778/>。仅监听本机。

默认范围“本次收录 · 249”。也可查看本次全部 1043 条轨迹或包含旧 4 件的 v6.3 收录 253 件。三个范围共 1047 个独立零件，相同零件跨范围共用一个标注。未交付重建 STEP 的记录仍保留轨迹及目标图，右侧明确显示“未交付重建 STEP”。

- `annotations/marks.json`：按 case 保存当前 `pass` / `fail` 与时间。原子写入，刷新和重启不会丢失。
- `annotations/history.jsonl`：每次变更的追加历史，记录前后标注。
- 原始轨迹、目标、重建和数据集均只读；网页不执行轨迹中的命令或 notebook，不自动将标注结果应用到训练集。
- 轨迹工具块参照 `cad-code/public/app.js` 的折叠方式。文本使用 DOM text nodes，原始完整 JSON 可下载。工具输出可展开全部内容；有 JSON 包装时另保留完整原始工具返回；工具媒体按原始 `callID` 对齐。接口未返回的思考不补写。
- 上一件/下一件可回看和修改标注；`←` / `→` 快捷键同导航按钮。保存失败留在当前件，显示错误，不自动跳过。
- 末件标完显示当前范围全部标注，右侧清空，不循环覆盖标签。
- 搜索、范围和状态筛选仅改变显示队列，不改变已有标签。

输入来自：`datasets/data-traj2/stepir-v6.3/index.jsonl` 与 `stepir_geom_gen/cadcode_synth_v63/out/*/verdict.json`。收录件优先使用打包目录的 `trajectory.json` / `target.step` / `rebuild.step`；其他本批件使用原始输出，缺 agent 导出时尝试独立复评的 `candidate.step`。

渲染由 `render_pairs.py`（SimpleCADAPI 2.2.7）生成，输出为 `images/<case>/target.png`、`rebuild.png` 与 `render.json`，后者记录源 STEP 哈希及相机。对比采用相同等测视角、并行投影和联合包围盒尺度。图片准备中会自动重试，点击图片可放大。进度见 `render-status.json`；渲染不修改原始文件。

API：`/api/catalog`、`/api/trajectory?case=...`、`/api/raw-trajectory?case=...`、`/api/image?case=...&kind=target|rebuild`、`/api/render-case?case=...`、`/api/artifact?case=...&kind=target|rebuild|model`、`GET/POST /api/marks`。标注写入需页面会话 token，并校验本机 Host / Origin；静态资源仅公开三个白名单文件，任意本地路径不通过 HTTP 暴露。

验证：在临时 `--annotations` 目录与独立随机端口检查了 249/1043/253 范围计数、1047 独立 case、完整消息与工具返回保留、原始轨迹下载、PNG、工具图片、两种标注写入/修改、修改历史、重启持久性、非法标签/来源拒绝。真实 `annotations/` 未写入测试标注。浏览器交互验收已完成：✅/❌自动下一件、刷新恢复、单件队列结束、空搜索、保存失败留当前，以及工具块展开。见 BROWSER_VALIDATION.json。

渲染已完成：1047 个唯一零件的目标图全部生成；967 件有重建图，80 件未交付可用 STEP。共有 20 件因 STEP 拓扑或根结构问题，使用 SDK XCAF 展示接口分别适配视口，页面注明“分别适配画面”；其余成对图使用联合包围盒相同尺度。源文件保持不变；详情见 RENDER_VALIDATION.json。
# 2026-11-10：扩展至 1572 条

正式网页：[http://127.0.0.1:8778/?scope=all](http://127.0.0.1:8778/?scope=all)。默认显示全部轨迹，可按批次或标注状态筛选；✅ / ❌ 保存后自动跳到下一条。

本次固定使用 2026-11-10 14:06 的统计快照：早期纯 v6.3 共 15 条、new-data 的 v6.3 批次 1268 条、data-1106 批次 257 条、934 重跑批次最先完成的 32 条，合计 1572 个不同会话。完整清单见 `catalog.json`，构建脚本为 `build_catalog.py`。后续新完成的重跑轨迹不会自动加入这份快照。

原来的 509 条人工标注完整保留（✅ 312、❌ 197），`annotations/marks.json` 与 `history.jsonl` 的哈希核对未变，并已备份至 `annotation-backups/`。新批次使用独立的轨迹标识，避免同一零件的新旧会话共享标注。浏览器测试使用独立的 `.qa/1572/annotations`，没有写入正式标注。

全部 1572 条轨迹与目标文件均可读取。全部 Target 等测图已生成；1451 条有 Rebuild 等测图，121 条源结果未交付任何可用重建 STEP，页面会明确显示缺失。图片逐一与源 STEP 哈希匹配，渲染失败数为 0。验证记录：`CATALOG_1572_VALIDATION.json`、`SITE_1572_VALIDATION.json`。

以下保留原版使用说明；其中原来的批次范围现由上述冻结清单代替。

# datav1 含思考轨迹标注视图（1772 条）

当前正式站点的活动数据范围只显示已确认的 datav1 轨迹：`http://127.0.0.1:8778/?scope=all` 或 `?scope=datav1`。Qwen 原生轨迹通过 `qwen_adapter.py` 转成网页读取格式，工具参数、工具结果、assistant 正文和 `reasoning_content` 均保留；每个思考段依据 `message_meta.reasoning_sources` 显示来源。Codex 事后补写的可见证据解释会标为“事后补写解释”，不伪装成原始隐藏思考。

本批总数 1772，ID 和思考内容来自正式 datav1 目录，Target PNG 从已有 datav1 标注缓存提供。源归档没有交付 rebuild STEP，故右侧如实显示未交付，不会运行历史 notebook 重建。删除的两条含图轨迹 `abc:00000027` 与 `abc:00000940` 不在本批中。

发布 datav1 目录前，旧 1572 条快照的目录原文备份为 `catalog-1572.json`，1572 个旧标签键与值均完整保留；datav1 轨迹使用 `datav1--<id>` 独立标注键，避免新批标签覆盖旧标签。网站重新只展示 datav1 后，原标签文件仍在原处，旧批标签不合并进 datav1 进度。后来发现并保留了用户在 datav1 批次上的实际标注，标签数量会持续增加。

数据清单由 `add_datav1_catalog.py` 构建，校验结果见 `DATAV1_1772_VALIDATION.json`。全量轨迹完成适配测试：1772/1772 成功，32300 次工具调用配对。思考来源统计：34073 段为 Codex 基于可见历史补写的解释，1 段为原始可见文本。数据集 README 表明轨迹语义质量仍待审核，网页只用于人类批注，不代表训练标签已批准。
