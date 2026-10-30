# ToFScope on macOS: setup

To run locally on macOS, you'll need an internet connection for setup, Git, and a folder containing one or more TOFexplorer `.h5` acquisitions. Installation downloads Python and dependencies as needed; the app itself runs locally and does not need Node.js or an account. Allow enough free space for the data and saved copies.

## Install

1. Open **Terminal** (Applications → Utilities → Terminal).
2. Install `uv` using the macOS instructions at [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/). Open a new Terminal window after installation and check:

   ```sh
   uv --version
   ```

3. Clone the repository and install ToFScope:

   ```sh
   git clone https://github.com/datasophos/ToFScope.git
   cd ToFScope
   uv tool install --python 3.12 .
   uv tool update-shell
   ```

   If Git is not installed, macOS may prompt you to install the Xcode Command Line Tools. Open a new Terminal window so the `tofscope` command is on your path.

## Start and use the app

Create a writable folder for saved analyses, then start the app. Replace the acquisition path below with your actual folder; keep the quotes if its path contains spaces.

```sh
mkdir -p "$HOME/Documents/ToFScope Saved"
tofscope --data-root "/path/to/acquisitions" --output-root "$HOME/Documents/ToFScope Saved"
```

Leave Terminal open while you work. The launcher opens the app in your browser once it is ready. To stop the app, return to Terminal and press **Control-C**. To start it again later, run the same `tofscope` command.

After performing some analyses, use the **Save as…** button to write your changes to a new file before stopping the app (stopping the app will cause you to lose your current changes). This creates a new HDF5 copy in the saved folder; the original acquisition is not changed. After restarting, reopening the version you saved in ToFScope will allow you to resume your analysis. Unsaved tabs and calculations will not survive a restart.

## Update or uninstall

For an update, save your work and stop ToFScope first. In the cloned repository, pull the latest changes and reinstall:

```sh
cd /path/to/ToFScope
git pull --ff-only
uv tool install --force --python 3.12 .
```

To uninstall the app, run `uv tool uninstall tofscope`. This does not delete your acquisition or saved-analysis folders.

## Troubleshooting

- **`uv: command not found`**: open a new Terminal window and follow the PATH instructions printed by the uv installer.
- **`tofscope: command not found`**: run `uv tool update-shell`, open a new Terminal window, and retry. `uv tool list` shows installed tools.
- **No files in the picker**: check that the `--data-root` path points to the folder containing the `.h5` files and that macOS grants Terminal access to it.
- **Browser did not open**: check Terminal for an error. If the service is running, `tofscope open` in another Terminal window opens the existing local service. Do not share its launch address.
- **Cannot save**: check that the output folder exists, is writable, and has enough free space for a full copy. Finish or cancel calculations and drafts before saving.
- **Port already in use or other startup errors**: stop the previous ToFScope process if it is still running. Run `tofscope doctor --data-root "/path/to/acquisitions" --output-root "$HOME/Documents/ToFScope Saved"` for diagnostics, and share the error with your support contact without sharing a launch address or secret.

For detailed configuration and deployment information, see [deployment](deployment.md).
