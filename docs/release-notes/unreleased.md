# Draft notes for a future release

## Portable Windows application

Download the Windows x64 ZIP from GitHub Releases, extract it, and open
`ToFScope.exe` to start ToFScope without installing Python. The launcher lets you
choose an acquisition folder, start and stop the local service, and open its log
and configuration file. The bundle can run offline after download. The executables
are unsigned, so Windows may show a SmartScreen warning.

## Configuration and memory limits

The Windows launcher creates a commented configuration file in the user's local
application data folder. Users can edit it to set options such as the output folder
and memory limits. Save changes and use Stop and Start in the launcher to apply them.

The default managed-memory and response limits are higher for large acquisitions.
Deployments can lower these limits in their configuration. The limits do not reserve
memory, and a computer can run out of memory before reaching them.
