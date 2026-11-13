# 数据格式

Catalog 是本地可信 JSON，包含 `rows` 数组。`case` 必须唯一、稳定、适合用作图片子目录名；不要包含目录分隔符。产物路径相对于 `--root`，也可使用可信绝对路径。仓库不捆绑真实 catalog。最小结构：

```json
{
  "schema_version": "stepir-review-catalog-v1",
  "rows": [{
    "case": "batch--part-001",
    "part_name": "Part 001",
    "batch": "example",
    "batch_label": "示例批次",
    "target": "artifacts/part-001/target.step",
    "rebuild": "artifacts/part-001/rebuild.step",
    "trajectory": "artifacts/part-001/trajectory.json",
    "model": "artifacts/part-001/model.py",
    "report": null,
    "riou": 0.999,
    "in_packed": false,
    "new_accepted": false
  }]
}
```

缺少的 rebuild、model、report 可以是 `null`。`target_image` 可引用历史 datav1 的既有 PNG；其他图片默认位于 `--images/CASE_ID/target.png` 和 `rebuild.png`。`render.json` 提供 `status`、`camera.fit` 和源文件 hash。

CAD Code 轨迹沿用 `cad-code-session-v2`：`messages[].info`、`messages[].parts`、`tool_media` 原样存储，读取显示时只将内联图片 URI 改为本站图片 endpoint。`/api/raw-trajectory` 下载原始文件字节。Qwen 格式的 row 标记 `trajectory_format: qwen`，适配器保留 `reasoning_content`、原 message index、工具参数/返回和 `message_meta.reasoning_sources`。

当前标签示例：

```json
{
  "batch--part-001": {
    "label": "pass",
    "updated_at": "2026-11-13T12:00:00+00:00"
  }
}
```

另一个有效值是 `fail`。每次保存还向 `history.jsonl` 追加 `case`、`previous`、`mark`。会话 token 仅用于浏览器本地写标签，不是模型 key。原始轨迹、目标和重建都不经 POST 修改。

## HTTP API

| 路径 | 内容 |
| --- | --- |
| `GET /api/catalog` | 显示行、已有标签及页面写入 token；不返回原始文件路径 |
| `GET /api/trajectory?case=...` | 适配后的显示结构 |
| `GET /api/raw-trajectory?case=...` | 原始 JSON 字节 |
| `GET /api/image?case=...&kind=target` | 预渲染 target/rebuild PNG |
| `GET /api/tool-image?case=...&media=0&part=0` | 对应工具调用的内联图像 |
| `GET /api/artifact?case=...&kind=model` | `target` / `rebuild` / `model` 原始文件 |
| `GET /api/render-case?case=...` | 当前件渲染 meta |
| `GET /api/marks` | 当前标签 |
| `POST /api/marks` | `case` / `label`；携带 `X-Review-Token`，沿用 Host / Origin 检查 |
