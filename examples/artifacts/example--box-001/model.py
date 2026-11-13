# /// script
# requires-python = ">=3.10"
# dependencies = ["simplecadapi==2.2.7"]
# [tool.simplecadapi]
# id = "model"
# revision = "1.0.0"
# ///
"""Synthetic viewer fixture, not a model-generated reconstruction."""
import marimo

app = marimo.App()

with app.setup:
    import simplecadapi as scad


@app.cell
def _():
    # ---- feature: example-box (build) ----
    body = scad.make_box_rsolid(width=20, height=12, depth=6)
    model = scad.Part(part_id="model", body=body)
    return (model,)


if __name__ == "__main__":
    app.run()
