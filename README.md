<p align="center">
  <img src="https://raw.githubusercontent.com/datasophos/ToFScope/main/docs/assets/tofscope-logo.svg" alt="ToFScope — FIB–SEM / TOF–SIMS" width="324">
</p>

# ToFScope

[![PyPI version](https://img.shields.io/pypi/v/tofscope)](https://pypi.org/project/tofscope/)

ToFScope is a browser-based application for exploring time-of-flight secondary ion mass spectrometry (ToF-SIMS) data. It allows you to analyze ion images, mass spectra, and depth profiles together so you can inspect an acquisition, compare signals, and save your analysis for later.

ToFScope runs locally as a Python application and opens in your browser. It reads [TOFWERK TOFexplorer](#trademark-disclaimer) HDF5 (`.h5`) acquisitions, and provides interactive tools for exploring their mass spectra, ion images, and depth profiles in two and three dimensions.

![ToFScope Explore showing an ion map, mass spectrum, front projection, and depth profile from a real acquisition](https://raw.githubusercontent.com/datasophos/ToFScope/main/docs/assets/tofscope-explore.png)

*Explore view showing an ion map, mass spectrum, front projection, and depth profile for a real acquisition.*

## What you can do

- **Explore an acquisition:** view ion maps, a mass spectrum, front projections, and depth profiles together; choose custom regions of interest and frame range.
- **Compare signals:** use stored ion channels or define custom mass windows from the spectrum, then compare their profiles.
- **Work with depth:** add calibration anchors to display profiles and projections in physical depth where calibration is known.
- **Inspect peaks and isotopes:** find candidate atomic isotope ions and measure selected signals over a region and frame range.
- **Visualize in 3D:** compare signals as volume overlays or tiled views, with controls for color, opacity, and threshold.
- **Keep and share results:** export profiles as CSV or plots as PNG, and save data back into TOFexplorer-compatible `.h5` files.

![ToFScope 3D visualizer showing an overlay of aluminum and titanium signals](https://raw.githubusercontent.com/datasophos/ToFScope/main/docs/assets/tofscope-3d.png)

*3D volume view comparing aluminum and titanium signals across acquisition frames.*

![Atomic identification dialog showing an aluminum-27 isotope candidate and mass spectrum](https://raw.githubusercontent.com/datasophos/ToFScope/main/docs/assets/tofscope-isotope-identification.png)

*Atomic identification compares a measured mass-to-charge ratio with candidate isotope ions.*

## Get started

You need Python 3.11 or newer, [uv](https://docs.astral.sh/uv/getting-started/installation/), and a folder containing supported TOFexplorer `.h5` files. Install from PyPI:

```sh
uv tool install tofscope
tofscope --data-root /path/to/acquisitions --output-root /path/to/saved-analyses
```

Replace the example paths with your folders. The output folder must be writable and have enough space for a full copy of an acquisition. ToFScope starts a local service and opens the app in your browser. Select a file to begin; keep the terminal open while you work and press **Ctrl-C** there to stop the app.

For step-by-step installation, folder setup, and troubleshooting, see [Install and launch](https://datasophos.github.io/ToFScope/docs/getting-started/installation.html). For configuration, hosted use, and containers, see [deployment](https://datasophos.github.io/ToFScope/docs/technical-documentation/deployment.html).

## Your first analysis

1. Open an acquisition and choose a stored signal, or create one from a mass window in the spectrum.
2. Select a frame range and region of interest to explore its ion image and depth profile. Add other signals to compare profiles.
3. Use **Depth calibration…** if you have known frame-to-depth measurements, or open **3D volume** to explore the signal spatially.
4. Choose **Save as…** to save a new analysis copy. After a restart, open it through **Saved files** to resume your saved work.

Saving leaves the source acquisition unchanged. Unsaved tabs and in-progress calculations do not survive a restart. Some raw files require preparation into a new copy before exploration; ToFScope previews that step and asks for confirmation.

The [user guide](https://datasophos.github.io/ToFScope/docs/getting-started/index.html) covers signals, calibration, exports, isotope identification, saving, and 3D controls in more detail.

## Current limitations

ToFScope is under active development and is in an alpha state. The application may change substantially prior to a stable 1.0.0 release.
See the [user guide](https://datasophos.github.io/ToFScope/docs/getting-started/index.html) for details.
If you have ideas of features to add, or notice any bugs, please open an [issue](https://github.com/datasophos/ToFScope/issues)!

Read the [documentation site](https://datasophos.github.io/ToFScope/) for guides, architecture diagrams, and deployment instructions.

## Developing ToFScope

The frontend is built with React and TypeScript; the service backend uses Python and FastAPI. Node.js is needed to develop or rebuild the frontend, but not to run the packaged application. From a source checkout:

```sh
uv sync --frozen
uv run tofscope --data-root /path/to/acquisitions --output-root /path/to/saved-analyses
```

For frontend and Python checks, build instructions, and distribution validation, see the [developer commands](https://datasophos.github.io/ToFScope/docs/technical-documentation/building-and-testing.html).

For a diagram-led overview of the application, see [how ToFScope works](https://datasophos.github.io/ToFScope/docs/technical-documentation/architecture.html).

To build or preview the documentation site, see [maintaining the documentation](https://datasophos.github.io/ToFScope/docs/technical-documentation/documentation.html).

## License

ToFScope is available under the [MIT License](https://github.com/datasophos/ToFScope/blob/main/LICENSE).

---

### Trademark disclaimer

TOFWERK and TOFexplorer are names owned by [TOFWERK AG](https://www.tofwerk.com/). They are used here solely to identify the products and file formats supported by ToFScope. ToFScope is an independent project and is not affiliated with, endorsed by, or sponsored by TOFWERK AG.
