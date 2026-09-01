AI Attribute Wrangle 1.0.3
Windows x64 / SideFX Houdini (tested with 21.0.440 / Python 3.11, 20.5, 20.0)

INSTALLATION (Choose any of the 3 methods below):

Option A — Professional GUI Setup Wizard (Recommended):
1. Extract this ZIP to a permanent folder on your workstation.
2. Double-click "Setup_AI_Wrangle.exe" (or "Setup_Wizard.py").
3. Select your target Houdini version(s) and click "🚀 Install AI Attribute Wrangle".
4. Restart Houdini.

Option B — 1-Click Drag-and-Drop (Inside Houdini, No Restart Needed):
1. Open Houdini.
2. Drag and drop "install_in_houdini.py" into your Houdini viewport or Python shell
   (or choose File -> Run Script -> select "install_in_houdini.py").
3. The node is live-installed immediately in your active session!

Option C — Studio Pipeline & Silent Batch Install:
1. Run "Install_AI_Wrangle.bat" from CMD/PowerShell for automated farm deployment.

USAGE:
In any Geometry network (/obj/geo), press TAB and type "AI Attribute Wrangle"
(or "ai_attribwrangle"). Enter your natural language prompt and click 🪄 Generate VEX!

REQUIREMENTS
- Windows 10/11 x64 and Houdini 21.0.x only. Other Houdini versions are not
  supported by this release.
- A Vulkan-capable GPU and sufficient VRAM for the bundled Q8 model. You may
  set AI_WRANGLE_GPU_LAYERS to reduce GPU offload for troubleshooting.
- At least 20 GB of free disk space for short-lived startup staging. First
  launch can take several minutes.

OPERATION AND PRIVACY
The normal product runtime starts a local loopback inference server. Prompts
and geometry context remain on the workstation. Ollama is not required. An
Ollama fallback exists only when a developer explicitly sets
AI_WRANGLE_ALLOW_OLLAMA_FALLBACK=1.
The encrypted model is staged to a randomly named temporary file with memory
mapping disabled, then the staging directory is removed once loading completes.

LIMITATIONS
AI-generated VEX must be reviewed before using it in production shots. The
tool compile-checks snippets, but compiling does not prove semantic correctness
or performance for every asset and scene.

SUPPORT
Include the contents of the Status field, Houdini version/build, Windows
version, GPU model/driver, and the release manifest hash when requesting help.
