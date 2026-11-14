ToFScope portable Windows test build

Extract the entire ZIP into a folder owned by your Windows account.
Keep both executables and the _internal folder together. No installation or
administrator privileges are required.

Double-click ToFScope.exe. Choose the folder containing your acquisitions,
then click Start. Your default browser opens when ToFScope is ready.
Keep the launcher open while you work. Use Open in browser to reopen the app.
Save your work before clicking Stop or closing the launcher.

The launcher remembers your acquisition folder. Preferences and logs are in
%LOCALAPPDATA%\ToFScope, outside this portable application folder.
Open log displays the service log; unexpected launcher errors are recorded
in launcher.log in the same directory. The service log is replaced on Start.

For command-line use, open Command Prompt in this folder and run:
  ToFScope-cli.exe --data-root "C:\path\to\acquisitions"
Press Ctrl+C in that console to stop the command-line service.
  ToFScope-cli.exe doctor --data-root "C:\path\to\acquisitions"
checks the configuration and bundled frontend.

To update, stop ToFScope, extract the new version into a separate folder,
and launch it there. Acquisition files and saved analyses should live outside
this application folder. Delete the old application folder when no longer needed.
This experimental build still requires Windows 10/11 testing.
