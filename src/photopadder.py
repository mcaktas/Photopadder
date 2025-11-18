import os
from pathlib import Path
from PIL import Image

import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser


# ------------ Core logic ------------

def compute_canvas_sizes_no_resize(size, short_side, long_side):
    """
    Given image size (w, h) and target aspect ratio short:long (e.g. 2:3),
    returns the minimal canvas (W, H) that:
      - keeps the original image size unchanged
      - only adds padding
      - has aspect ratio long/short on the long side.
    """
    w, h = size
    target_ratio = long_side / short_side

    if w >= h:
        # Landscape
        current_ratio = w / h
        if abs(current_ratio - target_ratio) < 1e-6:
            return w, h
        elif current_ratio > target_ratio:
            # too wide → increase height
            new_h = int((w / target_ratio) + 0.9999)
            new_w = w
        else:
            # too tall → increase width
            new_w = int((h * target_ratio) + 0.9999)
            new_h = h
    else:
        # Portrait
        current_ratio = h / w
        if abs(current_ratio - target_ratio) < 1e-6:
            return w, h
        elif current_ratio > target_ratio:
            # too tall → increase width
            new_w = int((h / target_ratio) + 0.9999)
            new_h = h
        else:
            # too wide → increase height
            new_h = int((w * target_ratio) + 0.9999)
            new_w = w

    return max(new_w, w), max(new_h, h)



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

    mode = img.mode if img.mode in ("RGB", "RGBA", "L") else "RGB"
    inner_canvas = Image.new(mode, (canvas_w, canvas_h), bg_color)

    offset_x = (canvas_w - img.width) // 2
    offset_y = (canvas_h - img.height) // 2
    inner_canvas.paste(img, (offset_x, offset_y))

    # Step 2 — optional outer border
    final_canvas = inner_canvas
    if border_percent and border_percent > 0:
        factor = 1 + border_percent
        final_w = int(canvas_w * factor)
        final_h = int(canvas_h * factor)

        final_canvas = Image.new(mode, (final_w, final_h), bg_color)
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
        root.title("Print Ready Pad")

        # ----- Menu Bar -----
        menubar = tk.Menu(root)

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Close", command=root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # About Menu
        about_menu = tk.Menu(menubar, tearoff=0)
        about_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="About", menu=about_menu)

        root.config(menu=menubar)
        # ----- End Menu Bar -----

        self.input_dir_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.border_var = tk.StringVar(value="0")

        self.preserve_extra_metadata_var = tk.BooleanVar(value=True)

        self.border_color_rgb = (255, 255, 255)
        self.border_color_hex = "#FFFFFF"

        # Aspect ratio options (short:long), special strings for Even/Custom
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

        # UI --- Input folder
        tk.Label(root, text="Input folder:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        tk.Entry(root, textvariable=self.input_dir_var, width=50).grid(row=0, column=1, padx=5, pady=3)
        tk.Button(root, text="Browse", command=self.browse_input).grid(row=0, column=2, padx=5, pady=3)

        # Output folder
        tk.Label(root, text="Output folder:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        tk.Entry(root, textvariable=self.output_dir_var, width=50).grid(row=1, column=1, padx=5, pady=3)
        tk.Button(root, text="Browse", command=self.browse_output).grid(row=1, column=2, padx=5, pady=3)

        # Select preset ratio
        tk.Label(root, text="Aspect ratio (short:long):").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.ratio_menu = tk.OptionMenu(root, self.ratio_label_var, *self.ratio_options.keys())
        self.ratio_menu.grid(row=2, column=1, sticky="w", padx=5, pady=3)

        # Custom ratio
        tk.Label(root, text="Custom ratio (e.g. 3:7):").grid(row=3, column=0, sticky="w", padx=5, pady=3)
        self.custom_ratio_entry = tk.Entry(root, textvariable=self.custom_ratio_var, width=10, state=tk.DISABLED)
        self.custom_ratio_entry.grid(row=3, column=1, sticky="w", padx=5, pady=3)

        # Extra border
        tk.Label(root, text="Extra border (%):").grid(row=4, column=0, sticky="w", padx=5, pady=3)
        tk.Entry(root, textvariable=self.border_var, width=10).grid(row=4, column=1, sticky="w", padx=5, pady=3)

        # Border color picker
        tk.Label(root, text="Padding color:").grid(row=5, column=0, sticky="w", padx=5, pady=3)
        self.color_label = tk.Label(root, text=self.border_color_hex, bg=self.border_color_hex, width=10)
        self.color_label.grid(row=5, column=1, sticky="w", padx=5, pady=3)
        tk.Button(root, text="Pick", command=self.pick_color).grid(row=5, column=2, padx=5, pady=3)

        # Metadata checkbox
        tk.Checkbutton(
            root,
            text="Preserve EXIF + DPI (ICC always preserved)",
            variable=self.preserve_extra_metadata_var,
        ).grid(row=6, column=0, columnspan=3, sticky="w", padx=5, pady=3)

        # Run
        tk.Button(root, text="Run", command=self.run, height=2).grid(row=7, column=0, columnspan=3, pady=10)

        self.status_label = tk.Label(root, text="", fg="blue")
        self.status_label.grid(row=8, column=0, columnspan=3, pady=5)

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

        msg = f"File exists:\n{filepath}\n\nOverwrite?"
        choice = messagebox.askyesnocancel("Overwrite?", msg)

        if choice is True:
            return True
        if choice is None:
            return None
        if choice is False:
            return False

    def show_about(self):
        import webbrowser

        top = tk.Toplevel(self.root)
        top.title("About Print Ready Pad")
        top.geometry("420x260")
        top.resizable(False, False)

        title = tk.Label(top, text="Print Ready Pad", font=("Arial", 14, "bold"))
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

    def run(self):
        input_dir = self.input_dir_var.get().strip()
        output_dir = self.output_dir_var.get().strip()
        border_str = self.border_var.get().strip()
        preserve_extra_metadata = self.preserve_extra_metadata_var.get()

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

        self.status_label.config(text="Processing...")
        self.root.update_idletasks()

        count = 0

        for fname in files:
            in_path = os.path.join(input_dir, fname)
            name, ext = os.path.splitext(fname)
            out_path = os.path.join(output_dir, f"{name}_padded{ext}")

            if os.path.exists(out_path):
                res = self.ask_overwrite(out_path)
                if res is None:
                    break
                if res is False:
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
                print(f"Error processing {fname}: {e}")

        self.status_label.config(text=f"Done! Processed {count} images.")
        messagebox.showinfo("Finished", f"Processed {count} images.")


if __name__ == "__main__":
    root = tk.Tk()
    app = PadApp(root)
    root.mainloop()
