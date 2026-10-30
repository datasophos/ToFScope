# ToFScope on macOS: setup

This guide is for a first installation with help from the person providing ToFScope. You need macOS, an internet connection for setup, a ToFScope wheel file, and a folder containing TOFexplorer `.h5` acquisitions. Installation downloads Python and dependencies as needed; the app itself runs locally and does not need Node.js or an account. Allow enough free space for the data and saved copies.

## Install

1. Open **Terminal** (Applications → Utilities → Terminal).
2. Install `uv` using the macOS instructions at [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/). Open a new Terminal window after installation and check:

   ```sh
   uv --version
   ```

3. Place the supplied `tofscope-0.2.0-py3-none-any.whl` in Downloads. Install it with:

   ```sh
   uv tool install --python 3.12 "$HOME/Downloads/tofscope-0.2.0-py3-none-any.whl"
   uv tool update-shell
   ```

   Open a new Terminal window so the `tofscope` command is on your path. If your wheel has a different filename, replace the filename in the command. Keep the wheel in a safe place in case you need to reinstall it.

## Start and use the app

Create a writable folder for saved analyses, then start the app. Replace the acquisition path below with your actual folder; keep the quotes if its path contains spaces. You can drag a folder from Finder into Terminal to insert its path.

```sh
mkdir -p "$HOME/Documents/ToFScope Saved"
tofscope --data-root "/path/to/acquisitions" --output-root "$HOME/Documents/ToFScope Saved"
```

Leave Terminal open while you work. The launcher opens the app in your browser once it is ready. Choose an acquisition in the file picker. To stop the app, return to Terminal and press **Control-C**. To start it again later, run the same `tofscope` command. The address and launch credentials are intended for your own computer; do not share them.

Use **Save as…** to keep your analysis before stopping the app. This creates a new HDF5 copy in the saved folder; the original acquisition is not changed. A copy contains the acquisition and can be larger than the original, so allow sufficient disk space. After restarting, open the copy through **Saved files** to resume committed work. Unsaved tabs and calculations do not survive a restart. Saved copies have not yet been verified for the unified save workflow in TOFexplorer.

## Update or uninstall

For an update, save your work and stop ToFScope first. Replace the filename with the new wheel supplied to you:

```sh
uv tool install --force --python 3.12 "$HOME/Downloads/tofscope-NEW_VERSION-py3-none-any.whl"
```

To uninstall the app, run `uv tool uninstall tofscope`. This does not delete your acquisition or saved-analysis folders. Keep the previous wheel if you may need to reinstall that version.

## Troubleshooting

- **`uv: command not found`**: open a new Terminal window and follow the PATH instructions printed by the uv installer.
- **`tofscope: command not found`**: run `uv tool update-shell`, open a new Terminal window, and retry. `uv tool list` shows installed tools.
- **No files in the picker**: check that the `--data-root` path points to the folder containing the `.h5` files and that macOS grants Terminal access to it.
- **Browser did not open**: check Terminal for an error. If the service is running, `tofscope open` in another Terminal window opens the existing local service. Do not share its launch address.
- **Cannot save**: check that the output folder exists, is writable, and has enough free space for a full copy. Finish or cancel calculations and drafts before saving.
- **Port already in use or other startup errors**: stop the previous ToFScope process if it is still running. Run `tofscope doctor --data-root "/path/to/acquisitions" --output-root "$HOME/Documents/ToFScope Saved"` for diagnostics, and share the error with your support contact without sharing a launch address or secret.

For detailed configuration and deployment information, see [deployment](deployment.md).
