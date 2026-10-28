"""Menu bar construction -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence
from PyQt6.QtWidgets import QMenuBar

from .... import theme
from ....xp_dialog import XPMessageBox
from .. import filters as filt, imageops as ops


class MenuMixin:
    """Menu bar construction."""

    def _act(self, menu, text, slot=None, shortcut=None, checkable=False, checked=False,
             enabled=True):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.setEnabled(enabled)
        if slot:
            action.triggered.connect(slot)
        else:
            action.triggered.connect(lambda: self._not_implemented(text))
        menu.addAction(action)
        self.addAction(action)
        return action

    def _not_implemented(self, label):
        clean = label.replace("&", "").rstrip(".")
        XPMessageBox.information(
            self, "PhotoChop",
            f"Could not complete the {clean} command because "
            f"of a program error.")

    def _build_menu(self):
        bar = QMenuBar()
        theme.style_menubar(bar)

        # ---- File
        m = bar.addMenu("&File")
        self._act(m, "&New...", self.new_file, "Ctrl+N")
        self._act(m, "&Open...", self.open_file, "Ctrl+O")
        self._act(m, "&Browse...", self.open_file_browser, "Ctrl+Shift+O")
        recent = m.addMenu("Open &Recent")
        self._act(recent, "Untitled-1.psd")
        self._act(recent, "final_FINAL_v3.psd")
        self._act(recent, "final_FINAL_v3 (use this one).psd")
        m.addSeparator()
        self._act(m, "&Close", self.close, "Ctrl+W")
        self._act(m, "&Save", self.save_file, "Ctrl+S")
        self._act(m, "Save &As...", self.save_file_as, "Ctrl+Shift+S")
        self._act(m, "Save for &Web...", self.save_for_web, "Ctrl+Alt+Shift+S")
        self._act(m, "Re&vert", self.revert, "F12")
        m.addSeparator()
        place = m.addMenu("&Place")
        self._act(place, "Place Image...", self.place_image)
        imp = m.addMenu("&Import")
        self._act(imp, "PDF Image...")
        self._act(imp, "Annotations...")
        self._act(imp, "WIA Support...")
        exp = m.addMenu("&Export")
        self._act(exp, "Paths to Illustrator...")
        self._act(exp, "ZoomView...")
        m.addSeparator()
        auto = m.addMenu("&Automate")
        self._act(auto, "Batch...", self.batch_dialog)
        self._act(auto, "Create Droplet...")
        self._act(auto, "Conditional Mode Change...")
        self._act(auto, "Contact Sheet II...")
        self._act(auto, "Fit Image...", self.fit_image)
        self._act(auto, "Multi-Page PDF to PSD...")
        self._act(auto, "Picture Package...")
        self._act(auto, "Web Photo Gallery...")
        m.addSeparator()
        self._act(m, "File &Info...", self.file_info)
        m.addSeparator()
        self._act(m, "Page Set&up...", self.page_setup, "Ctrl+Shift+P")
        self._act(m, "&Print with Preview...", self.print_preview, "Ctrl+P")
        self._act(m, "Print One Copy", self.print_one, "Ctrl+Alt+Shift+P")
        m.addSeparator()
        self._act(m, "Jump to ImageReady", self.jump_to_imageready, "Ctrl+Shift+M")
        m.addSeparator()
        self._act(m, "E&xit", self.close, "Ctrl+Q")

        # ---- Edit
        m = bar.addMenu("&Edit")
        self.undo_action = self._act(m, "&Undo", self.undo, "Ctrl+Z")
        self._act(m, "Step For&ward", self.redo, "Ctrl+Shift+Z")
        self._act(m, "Step &Backward", self.undo, "Ctrl+Alt+Z")
        m.addSeparator()
        self._act(m, "Fa&de...", self.fade, "Ctrl+Shift+F")
        m.addSeparator()
        self._act(m, "Cu&t", self.cut, "Ctrl+X")
        self._act(m, "&Copy", self.copy, "Ctrl+C")
        self._act(m, "Copy &Merged", self.copy_merged, "Ctrl+Shift+C")
        self._act(m, "&Paste", self.paste, "Ctrl+V")
        self._act(m, "Paste &Into", self.paste_into, "Ctrl+Shift+V")
        self._act(m, "Cle&ar", self.clear_selection_pixels)
        m.addSeparator()
        self._act(m, "Chec&k Spelling...", self.check_spelling)
        self._act(m, "Find and Replace Text...", self.find_replace)
        m.addSeparator()
        self._act(m, "&Fill...", self.fill_dialog, "Shift+F5")
        self._act(m, "&Stroke...", self.stroke_dialog)
        m.addSeparator()
        self._act(m, "Free Trans&form", lambda: self.canvas.begin_transform(), "Ctrl+T")
        tr = m.addMenu("&Transform")
        for label in ("Again", "Scale", "Rotate", "Skew", "Distort", "Perspective"):
            self._act(tr, label, lambda _=None, l=label: self.canvas.begin_transform(l))
        tr.addSeparator()
        self._act(tr, "Rotate 180°", lambda: self.canvas.transform_numeric(
            lambda i: ops.rotate(i, 180)))
        self._act(tr, "Rotate 90° CW", lambda: self.canvas.transform_numeric(
            lambda i: ops.rotate(i, 90)))
        self._act(tr, "Rotate 90° CCW", lambda: self.canvas.transform_numeric(
            lambda i: ops.rotate(i, -90)))
        self._act(tr, "Flip Horizontal", lambda: self.canvas.transform_numeric(
            lambda i: ops.flip(i, True)))
        self._act(tr, "Flip Vertical", lambda: self.canvas.transform_numeric(
            lambda i: ops.flip(i, False)))
        m.addSeparator()
        self._act(m, "Define Brush...", self.define_brush)
        self._act(m, "Define Pattern...", self.define_pattern)
        self._act(m, "Define Custom Shape...", self.define_shape)
        m.addSeparator()
        self._act(m, "Purge", self.purge)
        m.addSeparator()
        self._act(m, "Color Settings...", self.color_settings, "Ctrl+Shift+K")
        self._act(m, "Preset Manager...", self.preset_manager)
        prefs = m.addMenu("Pre&ferences")
        for page in ("General...", "File Handling...", "Display & Cursors...",
                     "Transparency & Gamut...", "Units & Rulers...",
                     "Guides, Grid & Slices...", "Plug-Ins & Scratch Disks...",
                     "Memory & Image Cache..."):
            self._act(prefs, page, lambda _=None, pg=page: self.preferences(pg))

        # ---- Image
        m = bar.addMenu("&Image")
        mode = m.addMenu("&Mode")
        self._mode_group = QActionGroup(self)
        for name in ("Bitmap", "Grayscale", "Duotone", "Indexed Color", "RGB Color",
                     "CMYK Color", "Lab Color", "Multichannel"):
            act = self._act(mode, name, lambda _=None, n=name: self.set_mode(n),
                            checkable=True, checked=(name == "RGB Color"))
            self._mode_group.addAction(act)
        mode.addSeparator()
        self._bit_depth_group = QActionGroup(self)
        self._bit_depth_group.setExclusive(True)
        self._bit_depth_actions = {}
        for depth in (8, 16):
            act = self._act(
                mode, f"{depth} Bits/Channel",
                lambda _=None, value=depth: self.set_bit_depth(value),
                checkable=True, checked=(depth == self.doc.bits_per_channel),
            )
            self._bit_depth_group.addAction(act)
            self._bit_depth_actions[depth] = act
        mode.addSeparator()
        self._act(mode, "Color Table...")
        self._act(mode, "Assign Profile...")
        self._act(mode, "Convert to Profile...")

        adjust = m.addMenu("Ad&justments")
        self._act(adjust, "&Levels...", self.levels, "Ctrl+L")
        self._act(adjust, "Auto Levels", self.auto_levels, "Ctrl+Shift+L")
        self._act(adjust, "Auto Contrast", self.auto_contrast, "Ctrl+Alt+Shift+L")
        self._act(adjust, "Auto Color", self.auto_color, "Ctrl+Shift+B")
        self._act(adjust, "&Curves...", self.curves, "Ctrl+M")
        self._act(adjust, "Color &Balance...", self.color_balance, "Ctrl+B")
        self._act(adjust, "Brightness/Contrast...", self.brightness_contrast)
        adjust.addSeparator()
        self._act(adjust, "&Hue/Saturation...", self.hue_saturation, "Ctrl+U")
        self._act(adjust, "&Desaturate", self.desaturate, "Ctrl+Shift+U")
        self._act(adjust, "Replace Color...", self.replace_color)
        self._act(adjust, "Selective Color...", self.selective_color)
        self._act(adjust, "Channel Mixer...", self.channel_mixer)
        self._act(adjust, "Gradient Map...", self.gradient_map)
        adjust.addSeparator()
        self._act(adjust, "&Invert", self.invert, "Ctrl+I")
        self._act(adjust, "Equalize", self.equalize)
        self._act(adjust, "Threshold...", self.threshold)
        self._act(adjust, "Posterize...", self.posterize)
        adjust.addSeparator()
        self._act(adjust, "Variations...", self.variations)

        m.addSeparator()
        self._act(m, "&Duplicate...", self.duplicate_document)
        self._act(m, "Apply Image...", self.apply_image)
        self._act(m, "Calculations...")
        m.addSeparator()
        self._act(m, "&Image Size...", self.image_size, "Ctrl+Alt+I")
        self._act(m, "&Canvas Size...", self.canvas_size, "Ctrl+Alt+C")
        rot = m.addMenu("&Rotate Canvas")
        self._act(rot, "180°", lambda: self.rotate_canvas(180))
        self._act(rot, "90° CW", lambda: self.rotate_canvas(90))
        self._act(rot, "90° CCW", lambda: self.rotate_canvas(-90))
        self._act(rot, "Arbitrary...", self.rotate_arbitrary)
        rot.addSeparator()
        self._act(rot, "Flip Horizontal", lambda: self.flip_canvas(True))
        self._act(rot, "Flip Vertical", lambda: self.flip_canvas(False))
        self._act(m, "Cro&p", self.crop_to_selection)
        self._act(m, "Trim...", self.trim)
        self._act(m, "Reveal All", self.reveal_all)
        m.addSeparator()
        self._act(m, "Histogram...", self.show_histogram)
        self._act(m, "Trap...")

        # ---- Layer
        m = bar.addMenu("&Layer")
        new = m.addMenu("&New")
        self._act(new, "Layer...", self.new_layer_dialog, "Ctrl+Shift+N")
        self._act(new, "Layer From Background", self.layer_from_background)
        self._act(new, "Layer Set...", self.new_layer_set)
        self._act(new, "Layer Set From Linked...")
        self._act(new, "Layer via Copy", self.layer_via_copy, "Ctrl+J")
        self._act(new, "Layer via Cut", self.layer_via_cut, "Ctrl+Shift+J")
        self._act(m, "&Duplicate Layer...", self.duplicate_layer)
        self._act(m, "De&lete Layer", self.delete_layer)
        m.addSeparator()
        self._act(m, "Layer &Properties...", self.layer_properties)
        style = m.addMenu("Layer &Style")
        self._act(style, "Blending Options...", self.layer_style)
        style.addSeparator()
        for effect in ("Drop Shadow", "Inner Shadow", "Outer Glow", "Inner Glow",
                       "Bevel and Emboss", "Satin", "Color Overlay", "Gradient Overlay",
                       "Pattern Overlay", "Stroke"):
            self._act(style, effect + "...",
                      lambda _=None, e=effect: self.layer_style(e))
        style.addSeparator()
        self._act(style, "Copy Layer Style", self.copy_layer_style)
        self._act(style, "Paste Layer Style", self.paste_layer_style)
        self._act(style, "Clear Layer Style", self.clear_layer_style)
        self._act(style, "Global Light...")
        self._act(style, "Create Layers", self.style_to_layers)
        self._act(style, "Hide All Effects", self.hide_effects)

        fill_new = m.addMenu("New &Fill Layer")
        for kind in ("Solid Color...", "Gradient...", "Pattern..."):
            self._act(fill_new, kind, lambda _=None, k=kind: self.new_fill_layer(k))
        adj_new = m.addMenu("New Ad&justment Layer")
        for kind in ("Levels...", "Curves...", "Color Balance...",
                     "Brightness/Contrast...", "Hue/Saturation...", "Selective Color...",
                     "Channel Mixer...", "Gradient Map...", "Invert", "Threshold...",
                     "Posterize..."):
            self._act(adj_new, kind,
                      lambda _=None, k=kind: self.new_adjustment_layer(k.rstrip(".")))
        self._act(m, "Change Layer Content")
        self._act(m, "Layer Content Options...")

        mask = m.addMenu("Add Layer &Mask")
        self._act(mask, "Reveal All", lambda: self.add_layer_mask("reveal"))
        self._act(mask, "Hide All", lambda: self.add_layer_mask("hide"))
        self._act(mask, "Reveal Selection", lambda: self.add_layer_mask("selection"))
        self._act(mask, "Hide Selection", lambda: self.add_layer_mask("hide-selection"))
        remove_mask = m.addMenu("&Remove Layer Mask")
        self._act(remove_mask, "Apply", lambda: self.remove_layer_mask(True))
        self._act(remove_mask, "Discard", lambda: self.remove_layer_mask(False))
        self._act(m, "Enable Layer Mask", self.toggle_layer_mask)
        m.addSeparator()
        self._act(m, "&Group with Previous", self.group_with_previous, "Ctrl+G")
        self._act(m, "&Ungroup", self.ungroup, "Ctrl+Shift+G")
        arrange = m.addMenu("&Arrange")
        self._act(arrange, "Bring to Front", lambda: self.arrange("front"), "Ctrl+Shift+]")
        self._act(arrange, "Bring Forward", lambda: self.arrange("forward"), "Ctrl+]")
        self._act(arrange, "Send Backward", lambda: self.arrange("backward"), "Ctrl+[")
        self._act(arrange, "Send to Back", lambda: self.arrange("back"), "Ctrl+Shift+[")
        align = m.addMenu("Align Linked")
        for label in ("Top Edges", "Vertical Centers", "Bottom Edges", "Left Edges",
                      "Horizontal Centers", "Right Edges"):
            self._act(align, label)
        m.addSeparator()
        self._act(m, "Merge &Down", self.merge_down, "Ctrl+E")
        self._act(m, "Merge &Visible", self.merge_visible, "Ctrl+Shift+E")
        self._act(m, "&Flatten Image", self.flatten_image)
        m.addSeparator()
        self._act(m, "Matting", self.defringe)

        # ---- Select
        m = bar.addMenu("&Select")
        self._act(m, "&All", self.select_all, "Ctrl+A")
        self._act(m, "&Deselect", self.deselect, "Ctrl+D")
        self._act(m, "&Reselect", self.reselect, "Ctrl+Shift+D")
        self._act(m, "&Inverse", self.inverse_selection, "Ctrl+Shift+I")
        m.addSeparator()
        self._act(m, "Color Range...", self.color_range)
        m.addSeparator()
        self._act(m, "&Feather...", self.feather, "Ctrl+Alt+D")
        modify = m.addMenu("&Modify")
        self._act(modify, "Border...", lambda: self.modify_selection("Border"))
        self._act(modify, "Smooth...", lambda: self.modify_selection("Smooth"))
        self._act(modify, "Expand...", lambda: self.modify_selection("Expand"))
        self._act(modify, "Contract...", lambda: self.modify_selection("Contract"))
        m.addSeparator()
        self._act(m, "&Grow", self.grow_selection)
        self._act(m, "Si&milar", self.similar_selection)
        m.addSeparator()
        self._act(m, "Transform Selection", self.transform_selection)
        m.addSeparator()
        self._act(m, "&Load Selection...", self.load_channel_selection)
        self._act(m, "&Save Selection...", self.save_selection_channel)

        # ---- Filter
        m = bar.addMenu("F&ilter")
        self.last_filter_action = self._act(m, "Last Filter", self.repeat_last_filter, "Ctrl+F")
        self.last_filter_action.setEnabled(False)
        m.addSeparator()
        self._act(m, "E&xtract...", self.extract, "Ctrl+Alt+X")
        self._act(m, "Li&quify...", self.liquify, "Ctrl+Shift+X")
        self._act(m, "&Pattern Maker...", self.pattern_maker, "Ctrl+Alt+Shift+X")
        m.addSeparator()
        for category, items in filt.FILTER_MENU:
            sub = m.addMenu(category)
            for label, key, params in items:
                self._act(sub, label,
                          lambda _=None, l=label, k=key, p=params: self.run_filter(l, k, p))

        # ---- View
        m = bar.addMenu("&View")
        proof = m.addMenu("Proof Setup")
        for label in ("Custom...", "Working CMYK", "Working Cyan Plate", "Macintosh RGB",
                      "Windows RGB", "Monitor RGB"):
            self._act(proof, label)
        self._act(m, "Proof Colors", shortcut="Ctrl+Y", checkable=True)
        self._act(m, "Gamut Warning", shortcut="Ctrl+Shift+Y", checkable=True)
        m.addSeparator()
        self._act(m, "Zoom &In", self.canvas_zoom_in, "Ctrl+=")
        self._act(m, "Zoom &Out", self.canvas_zoom_out, "Ctrl+-")
        self._act(m, "&Fit on Screen", self.canvas.fit_on_screen, "Ctrl+0")
        self._act(m, "&Actual Pixels", self.canvas.actual_pixels, "Ctrl+Alt+0")
        self._act(m, "Print Size", self.canvas.actual_pixels)
        m.addSeparator()
        self._act(m, "Show &Extras", self.toggle_extras, "Ctrl+H", checkable=True,
                  checked=True)
        show = m.addMenu("&Show")
        self._act(show, "Selection Edges", self.toggle_selection_edges,
                  checkable=True, checked=True)
        self._act(show, "Grid", self.toggle_grid, "Ctrl+'", checkable=True)
        self._act(show, "Guides", self.toggle_guides, "Ctrl+;", checkable=True, checked=True)
        self._act(show, "Slices", self.toggle_slices, checkable=True, checked=True)
        self._act(show, "Annotations", self.toggle_annotations,
                  checkable=True, checked=True)
        m.addSeparator()
        self._act(m, "&Rulers", self.toggle_rulers, "Ctrl+R", checkable=True, checked=True)
        m.addSeparator()
        self._act(m, "&Snap", self.toggle_snap, "Ctrl+Shift+;",
                  checkable=True, checked=True)
        self._act(m, "Lock Guides", self.toggle_guide_lock, "Ctrl+Alt+;", checkable=True)
        self._act(m, "Clear Guides", self.clear_guides)
        self._act(m, "New Guide...", self.new_guide)

        # ---- Window
        m = bar.addMenu("&Window")
        arrange_menu = m.addMenu("Arrange")
        self._act(arrange_menu, "Cascade")
        self._act(arrange_menu, "Tile")
        self._act(arrange_menu, "Arrange Icons")
        self._act(m, "Documents")
        m.addSeparator()
        self._act(m, "Workspace")
        m.addSeparator()
        self.palette_actions = {}
        for name in ("Tools", "Options", "File Browser", "Navigator", "Info", "Color",
                     "Swatches", "Styles", "History", "Actions", "Tool Presets",
                     "Layers", "Channels", "Paths", "Brushes", "Character",
                     "Paragraph", "Status Bar"):
            act = self._act(m, name, lambda _=None, n=name: self.toggle_palette(n),
                            checkable=True, checked=name not in ("File Browser",))
            self.palette_actions[name] = act

        # ---- Help
        m = bar.addMenu("&Help")
        self._act(m, "PhotoChop Help...", self.show_help, "F1")
        self._act(m, "About PhotoChop...", self.about)
        self._act(m, "About Plug-In", self.about_plugin)
        m.addSeparator()
        self._act(m, "Export Transparent Image...", self.help_wizard)
        self._act(m, "Resize Image...", self.help_wizard)
        m.addSeparator()
        self._act(m, "System Info...", self.system_info)
        self._act(m, "Updates, Support and more...", self.support)
        m.addSeparator()
        self._act(m, "Register...", self.register)
        self._act(m, "Transfer Activation...", self.deactivate)
        return bar
