import marimo

__generated_with = "0.25.1"
app = marimo.App(width="full", app_title="ToFScope")


@app.cell
def _():
    import os
    import marimo as mo
    from server_config import load_server_settings
    from workspace import ExplorerWorkspace
    return os, mo, load_server_settings, ExplorerWorkspace


@app.cell
def _(os, mo, load_server_settings, ExplorerWorkspace):
    try:
        settings = load_server_settings(os.environ)
        workspace = ExplorerWorkspace(settings.initial_file, settings=settings)
        view = mo.ui.anywidget(workspace)
    except (OSError,ValueError,KeyError) as exc:
        view = mo.callout(f'Cannot configure ToFScope: {exc}',kind='danger')
    view
    return


if __name__ == '__main__':
    app.run()
