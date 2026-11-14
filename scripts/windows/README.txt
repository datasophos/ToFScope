ToFScope Windows test build

Extract the entire ZIP to a writable folder. Open a Command Prompt in the
extracted folder and run:

  ToFScope.exe --data-root "C:\path\to\acquisitions"

The browser should open automatically. Keep the console open while using
ToFScope; press Ctrl+C to stop it. The data root must be an existing folder.
Run ToFScope.exe doctor --data-root "C:\path\to\acquisitions" to check the
configuration and bundled frontend. This experimental ZIP is not an installer.
