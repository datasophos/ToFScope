import marimo

__generated_with = "0.25.1"
app = marimo.App(width="full", app_title="ToFScope")


@app.cell
def _():
    import os
    import marimo as mo
    from explorer import DEFAULT_FILE
    from workspace import ExplorerWorkspace
    return os, mo, DEFAULT_FILE, ExplorerWorkspace


@app.cell
def _(os, mo, DEFAULT_FILE, ExplorerWorkspace):
    try:
        workspace = ExplorerWorkspace(os.environ.get('TOF_FILE',str(DEFAULT_FILE)))
        view = mo.ui.anywidget(workspace)
    except (OSError,ValueError,KeyError) as exc:
        view = mo.callout(f'Cannot open dataset: {exc}. Set TOF_FILE to a supported local HDF5 file.',kind='danger')
    view
    return


if __name__ == '__main__':
    app.run()
