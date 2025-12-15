import os
import math
from pathlib import Path
from PIL import Image

import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from tkinter import ttk




# ------------ Core logic ------------

def compute_canvas_sizes_no_resize(size, short_side, long_side):
    """
    Given image size (w, h) and target aspect ratio short:long (e.g. 2:3),
    returns the minimal canvas (W, H) that:
      - keeps the original image size unchanged
      - only adds padding
      - has the target aspect ratio (long/short)
    """
    w, h = size

    if w <= 0 or h <= 0:
        raise ValueError("Invalid image size")

    target_ratio = long_side / short_side
    current_ratio = w / h

    if abs(current_ratio - target_ratio) < 1e-6:
        return w, h

    if current_ratio > target_ratio:
        # Image is too wide → increase height
        new_w = w
        new_h = math.ceil(w / target_ratio)
    else:
        # Image is too tall → increase width
        new_h = h
        new_w = math.ceil(h * target_ratio)

    return new_w, new_h




def process_image(
    input_path,
    output_path,
    ratio_short,
    ratio_long,
    border_percent=0.0,
    bg_color=(255, 255, 255),
    preserve_extra_metadata=True,
    even_mode=False, ):
    """
    - Pads to desired aspect ratio without altering original image pixels,
      unless even_mode=True.
    - even_mode=True: no aspect padding, only optional outer border is added.
    - Adds optional outer border (%).
    - Always preserves ICC profile (for correct printing).
    - EXIF and DPI are optional (checkbox).
    """
    img = Image.open(input_path)

    exif = img.info.get("exif")
    icc_profile = img.info.get("icc_profile")
    dpi = img.info.get("dpi")

    # Step 1 — pad to aspect ratio or not (even_mode)
    if even_mode:
        canvas_w, canvas_h = img.size
    else:
        canvas_w, canvas_h = compute_canvas_sizes_no_resize(
            img.size, ratio_short, ratio_long
        )

    img_rgb = img.convert("RGB")

    inner_canvas = Image.new("RGB", (canvas_w, canvas_h), bg_color)

    offset_x = (canvas_w - img_rgb.width) // 2
    offset_y = (canvas_h - img_rgb.height) // 2

    inner_canvas.paste(img_rgb, (offset_x, offset_y))

    # Step 2 — optional outer border
    final_canvas = inner_canvas
    if border_percent and border_percent > 0:
        factor = 1 + border_percent
        final_w = math.ceil(canvas_w * factor)
        final_h = math.ceil(canvas_h * factor)

        final_canvas = Image.new("RGB", (final_w, final_h), bg_color)

        ox = (final_w - canvas_w) // 2
        oy = (final_h - canvas_h) // 2
        final_canvas.paste(inner_canvas, (ox, oy))

    # Prepare save kwargs
    save_kwargs = {}

    # Always preserve ICC
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile

    # Optional EXIF + DPI
    if preserve_extra_metadata:
        if exif:
            save_kwargs["exif"] = exif
        if dpi:
            save_kwargs["dpi"] = dpi

    ext = os.path.splitext(output_path)[1].lower()
    if ext in (".jpg", ".jpeg", ".webp"):
        save_kwargs["quality"] = 100

    final_canvas.save(output_path, **save_kwargs)


# ------------ GUI ------------

class PadApp:
    def __init__(self, root):
        self.root = root
        root.title("Photopadder")

        # Slightly nicer default size
        root.minsize(520, 380)

        # State variables
        self.input_dir_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.border_var = tk.StringVar(value="0")

        self.preserve_extra_metadata_var = tk.BooleanVar(value=True)

        self.border_color_rgb = (255, 255, 255)
        self.border_color_hex = "#FFFFFF"

        self.ratio_options = {
            "2:3 (classic 35mm)": (2, 3),
            "4:5 (common print)": (4, 5),
            "1:1 (square)": (1, 1),
            "Even (no ratio padding)": None,
            "Custom": None,
        }
        self.ratio_label_var = tk.StringVar(value="2:3 (classic 35mm)")
        self.custom_ratio_var = tk.StringVar()

        self.overwrite_all = False
        self.skip_all = False
        self.cancel_requested = False

        # ----- Menu Bar -----
        menubar = tk.Menu(root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Close", command=root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        about_menu = tk.Menu(menubar, tearoff=0)
        about_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="About", menu=about_menu)

        root.config(menu=menubar)
        # ----- End Menu Bar -----

        # Use a main frame for padding
        main = ttk.Frame(root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        # === Section 1: Source / Output ===
        src_frame = ttk.LabelFrame(main, text="Source & Destination", padding=10)
        src_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        src_frame.columnconfigure(1, weight=1)

        ttk.Label(src_frame, text="Input folder:").grid(row=0, column=0, sticky="w")
        ttk.Entry(src_frame, textvariable=self.input_dir_var, width=45).grid(
            row=0, column=1, sticky="ew", padx=5
        )
        ttk.Button(src_frame, text="Browse…", command=self.browse_input).grid(
            row=0, column=2
        )

        ttk.Label(src_frame, text="Output folder:").grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(src_frame, textvariable=self.output_dir_var, width=45).grid(
            row=1, column=1, sticky="ew", padx=5, pady=(5, 0)
        )
        ttk.Button(src_frame, text="Browse…", command=self.browse_output).grid(
            row=1, column=2, pady=(5, 0)
        )

        # === Section 2: Aspect & Border ===
        aspect_frame = ttk.LabelFrame(main, text="Aspect & Border", padding=10)
        aspect_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        aspect_frame.columnconfigure(1, weight=1)

        ttk.Label(aspect_frame, text="Aspect ratio:").grid(row=0, column=0, sticky="w")
        self.ratio_menu = ttk.OptionMenu(
            aspect_frame, self.ratio_label_var, self.ratio_label_var.get(), *self.ratio_options.keys()
        )
        self.ratio_menu.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(aspect_frame, text="Custom ratio (e.g. 3:7):").grid(
            row=1, column=0, sticky="w", pady=(5, 0)
        )
        self.custom_ratio_entry = ttk.Entry(
            aspect_frame, textvariable=self.custom_ratio_var, width=10, state=tk.DISABLED
        )
        self.custom_ratio_entry.grid(row=1, column=1, sticky="w", padx=5, pady=(5, 0))

        ttk.Label(aspect_frame, text="Extra border (%):").grid(
            row=2, column=0, sticky="w", pady=(5, 0)
        )
        ttk.Entry(aspect_frame, textvariable=self.border_var, width=10).grid(
            row=2, column=1, sticky="w", padx=5, pady=(5, 0)
        )

        ttk.Label(aspect_frame, text="Padding color:").grid(
            row=3, column=0, sticky="w", pady=(5, 0)
        )
        self.color_label = tk.Label(
            aspect_frame,
            text=self.border_color_hex,
            bg=self.border_color_hex,
            width=10,
            relief="groove",
            padx=5,
            pady=3
        )

        self.color_label.grid(row=3, column=1, sticky="w", padx=5, pady=(5, 0))
        ttk.Button(aspect_frame, text="Pick…", command=self.pick_color).grid(
            row=3, column=2, padx=5, pady=(5, 0)
        )

        # Manually fix ttk.Label background for color box
        # On some themes, background may be ignored; using regular tk.Label is also fine if needed.

        # === Section 3: Options & Run ===
        options_frame = ttk.LabelFrame(main, text="Options", padding=10)
        options_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        options_frame.columnconfigure(0, weight=1)

        ttk.Checkbutton(
            options_frame,
            text="Preserve EXIF + DPI (ICC always preserved)",
            variable=self.preserve_extra_metadata_var,
        ).grid(row=0, column=0, sticky="w")

        # Status + Run button row
        bottom_frame = ttk.Frame(main, padding=(0, 5, 0, 0))
        bottom_frame.grid(row=3, column=0, sticky="ew")
        bottom_frame.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(bottom_frame, text="", foreground="blue")
        self.status_label.grid(row=0, column=0, sticky="w")

        self.run_button = ttk.Button(bottom_frame, text="Run", command=self.run)
        self.run_button.grid(row=0, column=1, sticky="e", padx=(10, 0))

        self.cancel_button = ttk.Button(bottom_frame, text="Cancel", command=self.request_cancel, state=tk.DISABLED)
        self.cancel_button.grid(row=0, column=2, sticky="e", padx=(10, 0))

        # Progress bar (hidden until run)
        self.progress = ttk.Progressbar(main, mode="determinate")
        self.progress.grid(row=4, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.progress.grid_remove()  # hide initially

        # React to dropdown changes (enable/disable custom ratio)
        self.ratio_label_var.trace_add("write", self.on_ratio_change)

    def on_ratio_change(self, *args):
        label = self.ratio_label_var.get()
        if label == "Custom":
            self.custom_ratio_entry.config(state=tk.NORMAL)
        else:
            self.custom_ratio_entry.config(state=tk.DISABLED)

    def browse_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_dir_var.set(folder)

    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir_var.set(folder)

    def pick_color(self):
        color = colorchooser.askcolor(initialcolor=self.border_color_hex)
        if color and color[0]:
            (r, g, b), hex_color = color
            self.border_color_rgb = (int(r), int(g), int(b))
            self.border_color_hex = hex_color
            self.color_label.config(text=hex_color, bg=hex_color)

    def ask_overwrite(self, filepath):
        if self.overwrite_all:
            return True
        if self.skip_all:
            return False

        result = {"choice": None}

        dialog = tk.Toplevel(self.root)
        dialog.title("File exists")
        dialog.resizable(False, False)
        dialog.grab_set()  # modal

        tk.Label(
            dialog,
            text=f"File already exists:\n\n{filepath}",
            justify="left",
            wraplength=380,
        ).pack(padx=15, pady=(15, 10))

        def choose(value):
            result["choice"] = value
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Overwrite", width=14,
                   command=lambda: choose("overwrite")).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Skip", width=14,
                   command=lambda: choose("skip")).grid(row=0, column=1, padx=5)

        ttk.Button(btn_frame, text="Overwrite all", width=14,
                   command=lambda: choose("overwrite_all")).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(btn_frame, text="Skip all", width=14,
                   command=lambda: choose("skip_all")).grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(dialog, text="Cancel", width=12,
                   command=lambda: choose("cancel")).pack(pady=(0, 10))

        self.root.wait_window(dialog)

        choice = result["choice"]

        if choice == "overwrite":
            return True
        if choice == "skip":
            return False
        if choice == "overwrite_all":
            self.overwrite_all = True
            return True
        if choice == "skip_all":
            self.skip_all = True
            return False

        return None  # cancel

    def show_about(self):
        import webbrowser

        top = tk.Toplevel(self.root)
        top.title("Photopadder")
        top.geometry("420x260")
        top.resizable(False, False)

        title = tk.Label(top, text="Photopadder", font=("Arial", 14, "bold"))
        title.pack(pady=(10, 0))

        subtitle = tk.Label(top, text="A simple tool for adding clean borders and print-ready ratios.",
                            font=("Arial", 10))
        subtitle.pack(pady=(0, 10))

        # Description
        desc = (
            "• Pad images to any aspect ratio (or keep original)\n"
            "• Never resizes or crops your photo\n"
            "• Always preserves ICC profile for correct printing\n"
            "• Optional EXIF + DPI retention"
        )
        tk.Label(top, text=desc, justify="left").pack(pady=5)

        # GitHub link
        def open_github():
            webbrowser.open("https://github.com/mcaktas/Photopadder")

        github_link = tk.Label(top, text="GitHub Repository", fg="blue", cursor="hand2")
        github_link.pack()
        github_link.bind("<Button-1>", lambda e: open_github())




        tk.Button(top, text="Close", command=top.destroy).pack(pady=10)

    def set_busy(self, busy: bool):
        self.run_button.config(state=(tk.DISABLED if busy else tk.NORMAL))
        self.cancel_button.config(state=(tk.NORMAL if busy else tk.DISABLED))
        self.root.config(cursor=("watch" if busy else ""))
        self.root.update()  # process UI events immediately

    def request_cancel(self):
        self.cancel_requested = True
        self.status_label.config(text="Cancelling… (finishing current file)")
        self.root.update()  # ensure message appears instantly

    def run(self):
        input_dir = self.input_dir_var.get().strip()
        output_dir = self.output_dir_var.get().strip()
        border_str = self.border_var.get().strip()
        preserve_extra_metadata = self.preserve_extra_metadata_var.get()
        self.overwrite_all = False
        self.skip_all = False
        self.cancel_requested = False

        if not os.path.isdir(input_dir):
            messagebox.showerror("Error", "Invalid input folder.")
            return

        if not output_dir:
            messagebox.showerror("Error", "Select an output folder.")
            return

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        try:
            border_percent = float(border_str) / 100.0 if border_str else 0.0
        except:
            messagebox.showerror("Error", "Invalid border % value.")
            return

        label = self.ratio_label_var.get()

        even_mode = False
        ratio_short = 2.0
        ratio_long = 3.0

        if label == "Even (no ratio padding)":
            even_mode = True
        elif label == "Custom":
            custom = self.custom_ratio_var.get().strip()
            if not custom:
                messagebox.showerror("Error", "Please enter a custom ratio (e.g. 3:7).")
                return
            try:
                s, l = custom.split(":")
                ratio_short, ratio_long = float(s), float(l)
            except:
                messagebox.showerror("Error", "Invalid custom ratio. Use format e.g. 3:7")
                return
        else:
            ratio_short, ratio_long = self.ratio_options[label]

        files = [
            f for f in os.listdir(input_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".tif", ".tiff", ".png", ".webp"))
        ]

        if not files:
            messagebox.showinfo("Info", "No images found.")
            return

        files.sort()  # deterministic order

        self.set_busy(True)

        count = 0
        total = len(files)
        cancelled = False
        failed = []  # list of (filename, error_message)

        self.progress.config(maximum=total, value=0)
        self.progress.grid()
        self.status_label.config(text=f"Processing 0/{total}...")
        self.root.update()


        try:
            for i, fname in enumerate(files, start=1):
                if self.cancel_requested:
                    cancelled = True
                    break
                in_path = os.path.join(input_dir, fname)
                name, ext = os.path.splitext(fname)
                out_path = os.path.join(output_dir, f"{name}_padded{ext}")

                if os.path.exists(out_path):
                    res = self.ask_overwrite(out_path)
                    if res is None:
                        cancelled = True
                        break
                    if res is False:
                        self.progress["value"] = i
                        self.status_label.config(text=f"Skipping {i}/{total}: {fname}")
                        self.root.update()

                        continue

                try:
                    process_image(
                        in_path,
                        out_path,
                        ratio_short=ratio_short,
                        ratio_long=ratio_long,
                        border_percent=border_percent,
                        bg_color=self.border_color_rgb,
                        preserve_extra_metadata=preserve_extra_metadata,
                        even_mode=even_mode,
                    )
                    count += 1
                except Exception as e:
                    err = str(e) or repr(e)
                    failed.append((fname, err))
                    print(f"Error processing {fname}: {err}")

                self.progress["value"] = i
                self.status_label.config(text=f"{i}/{total}: {fname}")
                self.root.update()

        finally:
            self.progress.grid_remove()
            self.set_busy(False)

        title = "Cancelled" if cancelled else "Finished"
        status_prefix = "Cancelled." if cancelled else "Done!"

        if failed:
            lines = [f"Processed: {count}", f"Failed: {len(failed)}", ""]
            lines.append("Failed files:")
            for fname, err in failed[:20]:
                lines.append(f"• {fname} — {err}")
            if len(failed) > 20:
                lines.append(f"...and {len(failed) - 20} more.")

            msg = "\n".join(lines)
            self.status_label.config(
                text=f"{status_prefix} Processed {count}, failed {len(failed)}."
            )
            messagebox.showwarning(f"{title} (with errors)", msg)
        else:
            self.status_label.config(text=f"{status_prefix} Processed {count} images.")
            messagebox.showinfo(title, f"Processed {count} images.")


if __name__ == "__main__":
    root = tk.Tk()
    app = PadApp(root)
    root.mainloop()
