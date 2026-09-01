# Developer release procedure — v1.0.3

The RSA private key and customer licenses are intentionally excluded from this
project. Keep the private key in a protected local vault or managed secrets
service; never copy it into `commercial_build`, `dist`, or a source archive.

Set `AI_WRANGLE_PRIVATE_KEY` to its secure path before issuing a license. If
the key is password protected, set `AI_WRANGLE_PRIVATE_KEY_PASSWORD` only for
the issuing session. Issue each customer license using their Machine ID:

```powershell
$env:AI_WRANGLE_PRIVATE_KEY = "C:\secure\developer_master_private_key.pem"
python commercial_build/developer_tools/issue_customer_license.py `
  "Customer Name" "ORDER-123" "VEX-XXXX-XXXX-XXXX" "C:\delivery\ai_wrangle.lic"
```

Every model delivery is customer-specific. Issue the signed license first, then
build a vault bound cryptographically to both that license and the customer's Machine ID:

```powershell
python commercial_build/package_builder.py --customer-license C:\delivery\ai_wrangle.lic --acknowledge-offline-model-risk
```

The build compiles all Python modules into native C-extensions (`.pyd`), bundles
the complete standalone runtime (`bin/llama-server.exe` + `mtmd.dll` + all 22 DLLs),
encrypts the model vault (`models/vex_brain.dat`), and packages the professional
installers:
- `Setup_AI_Wrangle.exe` (Native Win32 GUI Setup Wizard)
- `Setup_Wizard.py` (Tkinter Setup & License Manager)
- `install_in_houdini.py` (In-Houdini 1-Click Drag-and-Drop Installer)

Run `verify_release.py` with the generated package directory, ZIP, and `hython.exe`:

```powershell
python commercial_build/verify_release.py dist/AI_Attribute_Wrangle_v1.0.2 --hython "C:\Program Files\Side Effects Software\Houdini 21.0.440\bin\hython.exe"
```

Before release, test the release package on a clean supported workstation and
publish the ZIP SHA-256 on your verified download page.
