"""
=============================================================================
 AI Attribute Wrangle — Free Community Edition Setup Wizard
 Zero external dependencies (uses standard Python Tkinter).
=============================================================================
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path


def discover_houdini_preferences() -> list[tuple[str, Path]]:
    found = []
    seen_paths = set()

    search_roots = [
        Path(os.path.expanduser("~/Documents")),
        Path(os.path.expanduser("~/OneDrive/Documents")),
        Path(os.getenv("USERPROFILE", "")) / "Documents",
        Path(os.getenv("USERPROFILE", "")) / "OneDrive" / "Documents",
        Path(os.getenv("ONEPROFILE", "")) / "Documents",
    ]

    custom_pref = os.getenv("HOUDINI_USER_PREF_DIR")
    if custom_pref:
        search_roots.insert(0, Path(custom_pref).parent)

    for root in search_roots:
        if not root or not root.exists():
            continue
        try:
            for item in root.glob("houdini*"):
                if item.is_dir() and item.name.startswith("houdini"):
                    resolved = item.resolve()
                    if resolved not in seen_paths:
                        seen_paths.add(resolved)
                        ver_name = item.name.replace("houdini", "Houdini ").strip()
                        found.append((f"{ver_name} ({item.parent.name}/{item.name})", resolved))
        except Exception:
            continue

    found.sort(key=lambda x: str(x[1].name), reverse=True)
    return found


def install_package_for_target(plugin_root: Path, target_pref_dir: Path) -> tuple[bool, str]:
    try:
        packages_dir = target_pref_dir / "packages"
        packages_dir.mkdir(parents=True, exist_ok=True)
        json_path = packages_dir / "ai_attribwrangle.json"

        fwd_root = plugin_root.as_posix()
        package_def = {
            "hpath": fwd_root,
            "env": [
                {"PYTHONPATH": f"{fwd_root}/python;$PYTHONPATH"},
                {"PATH": f"{fwd_root}/bin;$PATH"},
                {"AI_WRANGLE_ROOT": fwd_root},
            ]
        }

        json_path.write_text(json.dumps(package_def, indent=2) + "\n", encoding="utf-8")
        return True, str(json_path)
    except Exception as e:
        return False, str(e)


def uninstall_package_for_target(target_pref_dir: Path) -> tuple[bool, str]:
    try:
        json_path = target_pref_dir / "packages" / "ai_attribwrangle.json"
        if json_path.exists():
            json_path.unlink()
            return True, f"Removed {json_path}"
        return True, "No existing installation found in target."
    except Exception as e:
        return False, str(e)


class SetupWizardApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AI Attribute Wrangle — Setup Wizard")
        self.root.geometry("620x560")
        self.root.minsize(560, 500)
        self.root.configure(bg="#1e1e24")

        if getattr(sys, "frozen", False):
            self.plugin_root = Path(sys.executable).resolve().parent
        else:
            self.plugin_root = Path(__file__).resolve().parent
            if (self.plugin_root / "python").exists() or (self.plugin_root / "otls").exists():
                pass
            elif (self.plugin_root.parent / "dist" / "AI_Attribute_Wrangle_v1.0.2").exists():
                self.plugin_root = self.plugin_root.parent / "dist" / "AI_Attribute_Wrangle_v1.0.2"

        self.houdini_versions = discover_houdini_preferences()
        self.version_vars = {}

        self._init_style()
        self._build_ui()

    def _init_style(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background="#1e1e24", foreground="#f0f0f0", font=("Segoe UI", 9))

    def _build_ui(self):
        header_frame = tk.Frame(self.root, bg="#141418", height=80)
        header_frame.pack(fill="x", side="top")

        title_lbl = tk.Label(
            header_frame, text="⚡ AI Attribute Wrangle", font=("Segoe UI", 15, "bold"),
            bg="#141418", fg="#ff8800"
        )
        title_lbl.pack(anchor="w", padx=20, pady=(12, 2))

        sub_lbl = tk.Label(
            header_frame, text="Offline AI Copilot for SideFX Houdini • Free Edition (Zero License Needed)",
            font=("Segoe UI", 9), bg="#141418", fg="#88ff88"
        )
        sub_lbl.pack(anchor="w", padx=20, pady=(0, 12))

        main_frame = tk.Frame(self.root, bg="#1e1e24")
        main_frame.pack(fill="both", expand=True, padx=20, pady=15)

        # Status Banner
        status_frame = tk.Frame(main_frame, bg="#282830", padx=12, pady=8)
        status_frame.pack(fill="x", pady=(0, 12))
        tk.Label(
            status_frame, text="✨ Free Edition — Fully Unlocked & Offline Ready",
            font=("Segoe UI", 10, "bold"), bg="#282830", fg="#00ffcc"
        ).pack(anchor="w")
        tk.Label(
            status_frame, text="No license keys or activation required. Ready to run directly in Houdini.",
            font=("Segoe UI", 8), bg="#282830", fg="#aaaaaa"
        ).pack(anchor="w")

        # Houdini Version Selection Section
        ver_frame = tk.LabelFrame(
            main_frame, text=" 🎯 Target Houdini Version(s) ",
            font=("Segoe UI", 9, "bold"), bg="#282830", fg="#ff9922", padx=12, pady=10
        )
        ver_frame.pack(fill="both", expand=True, pady=(0, 12))

        if self.houdini_versions:
            info_lbl = tk.Label(ver_frame, text="Detected Houdini preference directories:", bg="#282830", fg="#cccccc")
            info_lbl.pack(anchor="w", pady=(0, 6))

            for label, path in self.houdini_versions:
                var = tk.BooleanVar(value=True)
                self.version_vars[path] = var
                cb = tk.Checkbutton(
                    ver_frame, text=label, variable=var, bg="#282830", fg="#ffffff",
                    activebackground="#282830", activeforeground="#ff8800", selectcolor="#181820",
                    font=("Segoe UI", 9)
                )
                cb.pack(anchor="w", pady=2)
        else:
            no_ver_lbl = tk.Label(
                ver_frame, text="⚠️ No Houdini preference folders detected automatically.\nClick 'Browse Custom Preference Directory...' below.",
                bg="#282830", fg="#ffaa33", justify="left"
            )
            no_ver_lbl.pack(anchor="w", pady=6)

        browse_btn = tk.Button(
            ver_frame, text="📂 Browse Custom Houdini Directory...", font=("Segoe UI", 8),
            bg="#33333e", fg="#ffffff", activebackground="#444455", relief="flat", padx=8, pady=2,
            command=self._browse_custom_houdini_dir
        )
        browse_btn.pack(anchor="w", pady=(6, 0))

        # Action Buttons & Log
        action_frame = tk.Frame(main_frame, bg="#1e1e24")
        action_frame.pack(fill="x", pady=(0, 8))

        install_btn = tk.Button(
            action_frame, text="🚀 1-Click Install AI Attribute Wrangle", font=("Segoe UI", 11, "bold"),
            bg="#ff6600", fg="#ffffff", activebackground="#ff8822", activeforeground="#ffffff",
            relief="flat", pady=8, cursor="hand2", command=self._perform_install
        )
        install_btn.pack(fill="x", pady=(0, 6))

        uninst_btn = tk.Button(
            action_frame, text="Uninstall / Remove Package Definition", font=("Segoe UI", 8),
            bg="#2a2a32", fg="#aa8888", activebackground="#3a3a44", activeforeground="#ff8888",
            relief="flat", pady=2, command=self._perform_uninstall
        )
        uninst_btn.pack(fill="x")

        # Status Log Box
        self.log_box = tk.Text(
            main_frame, height=3, font=("Consolas", 8), bg="#141418", fg="#88ff88",
            relief="flat", highlightthickness=1, highlightbackground="#333344"
        )
        self.log_box.pack(fill="x", pady=(6, 0))
        self._log(f"Plugin Root: {self.plugin_root.as_posix()}")

    def _log(self, text: str):
        self.log_box.insert("end", f"• {text}\n")
        self.log_box.see("end")

    def _browse_custom_houdini_dir(self):
        dirpath = filedialog.askdirectory(title="Select Houdini Preference Directory (e.g. Documents/houdini21.0)")
        if dirpath:
            p = Path(dirpath).resolve()
            if p not in self.version_vars:
                var = tk.BooleanVar(value=True)
                self.version_vars[p] = var
                self.houdini_versions.append((f"Custom: {p.name} ({p})", p))
                self._log(f"Added custom directory: {p}")
                messagebox.showinfo("Directory Added", f"Added custom Houdini target:\n{p}")

    def _perform_install(self):
        selected_paths = [path for path, var in self.version_vars.items() if var.get()]
        if not selected_paths:
            messagebox.showwarning("No Targets Selected", "Please select at least one Houdini directory to install into.")
            return

        success_count = 0
        for path in selected_paths:
            ok, msg = install_package_for_target(self.plugin_root, path)
            if ok:
                success_count += 1
                self._log(f"Installed into {path.name}: {msg}")
            else:
                self._log(f"Failed {path.name}: {msg}")

        if success_count > 0:
            msg = (
                f"🎉 Successfully installed AI Attribute Wrangle into {success_count} Houdini version(s)!\n\n"
                "Next Steps:\n"
                "1. Start / Restart SideFX Houdini.\n"
                "2. In any Geometry Network (/obj/geo), press TAB and type 'AI Attribute Wrangle' or 'ai_attribwrangle'.\n"
                "3. Type your prompt and click 🪄 Generate VEX!"
            )
            messagebox.showinfo("Installation Complete", msg)
        else:
            messagebox.showerror("Installation Failed", "Could not write package definitions. Check folder permissions.")

    def _perform_uninstall(self):
        if not messagebox.askyesno("Confirm Uninstall", "Remove AI Attribute Wrangle package definitions from selected Houdini versions?"):
            return

        selected_paths = [path for path, var in self.version_vars.items() if var.get()]
        count = 0
        for path in selected_paths:
            ok, msg = uninstall_package_for_target(path)
            if ok:
                count += 1
                self._log(f"Uninstalled from {path.name}")
        messagebox.showinfo("Uninstalled", f"Removed package definitions from {count} Houdini version(s).")


def main():
    root = tk.Tk()
    app = SetupWizardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
