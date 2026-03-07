#!/usr/bin/env python3
# Nova Files - Modern File Manager
# VERSION: v4.2.3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, Pango, GObject
try:
    from gi.repository import GdkPixbuf
except: GdkPixbuf = None
import os, subprocess, json, shutil, colorsys, threading, math, webbrowser, urllib.parse
from pathlib import Path
from datetime import datetime

CFG_DIR = os.path.expanduser("~/.config/nova-files")
CFG_PATH = os.path.join(CFG_DIR, "settings.json")
CUSTOM_CSS = os.path.join(CFG_DIR, "custom.css")
QA_PATH = os.path.join(CFG_DIR, "quick_access.json")
RECENTS_PATH = os.path.join(CFG_DIR, "recents.json")
PI2 = math.pi * 2
MAX_RECENTS = 30

def load_quick_access():
    try:
        with open(QA_PATH) as f: return json.load(f)
    except: return []

def save_quick_access(items):
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(QA_PATH, 'w') as f: json.dump(items, f, indent=2)

def load_recents():
    try:
        with open(RECENTS_PATH) as f: return json.load(f)
    except: return []

def save_recents(items):
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(RECENTS_PATH, 'w') as f: json.dump(items[:MAX_RECENTS], f, indent=2)

def add_recent(filepath):
    recents = load_recents()
    fp = str(filepath)
    recents = [r for r in recents if r["path"] != fp]
    recents.insert(0, {"path": fp, "time": datetime.now().isoformat()})
    save_recents(recents[:MAX_RECENTS])

DEFAULT = {"accent_r":136,"accent_g":130,"accent_b":255,"theme":"nova","ui_scale":1.3,
    "icon_size_list":22,"icon_size_grid":48,"row_height":38,
    "font_family":"system-ui","font_size":13,"icon_style":"system","light_mode":False,
    "perf_mode":"normal"}

# Cloud drive detection — checks GVFS mounts (like Nautilus) + local sync folders
def detect_cloud_folders():
    clouds = []
    home = str(Path.home())
    uid = os.getuid()
    gvfs_dir = f"/run/user/{uid}/gvfs"
    if os.path.isdir(gvfs_dir):
        try:
            for entry in os.listdir(gvfs_dir):
                full = os.path.join(gvfs_dir, entry)
                if not os.path.isdir(full): continue
                if entry.startswith("google-drive:"):
                    parts = dict(p.split("=",1) for p in entry.split(",") if "=" in p)
                    user = parts.get("user", "")
                    label = f"Google Drive"
                    if user: label = f"{user}"
                    clouds.append({"name": label, "path": full, "type": "gdrive"})
                elif "onedrive" in entry.lower():
                    clouds.append({"name": "OneDrive", "path": full, "type": "onedrive"})
                elif "nextcloud" in entry.lower():
                    clouds.append({"name": "Nextcloud", "path": full, "type": "nextcloud"})
        except: pass
    found_types = {c["type"] for c in clouds}
    for name, ctype, paths in [
        ("OneDrive", "onedrive", ["OneDrive", "OneDrive - Personal", ".local/share/onedrive"]),
        ("Google Drive", "gdrive", ["Google Drive", "google-drive", ".local/share/google-drive"]),
        ("Dropbox", "dropbox", ["Dropbox"]),
    ]:
        if ctype in found_types: continue
        for p in paths:
            full = os.path.join(home, p)
            if os.path.isdir(full):
                clouds.append({"name": name, "path": full, "type": ctype})
                break
    # v2.9.5: Detect rclone mounts
    rclone_cloud_dir = os.path.join(CFG_DIR, "cloud")
    if os.path.isdir(rclone_cloud_dir):
        for entry in os.listdir(rclone_cloud_dir):
            full = os.path.join(rclone_cloud_dir, entry)
            if not os.path.isdir(full): continue
            if any(c["path"] == full for c in clouds): continue
            if "onedrive" in entry.lower():
                if "onedrive" not in found_types:
                    clouds.append({"name": "OneDrive", "path": full, "type": "onedrive"})
            elif "google" in entry.lower() or "gdrive" in entry.lower():
                if "gdrive" not in found_types:
                    clouds.append({"name": "Google Drive", "path": full, "type": "gdrive"})
    return clouds


# Themes: colors + UI shape rules + recommended accent
# Each has dark (default) + light variant
THEMES = {
    "nova":    {"name":"Nova","bg":"#1a1a1e","sbg":"#131316","fg":"255,255,255","ba":0.04,
                "lbg":"#f4f4f8","lsbg":"#eaeaef","lfg":"0,0,0","lba":0.08,
                "sel":"fill","sel_radius":10,"row_pad":4,"sidebar_radius":10,"icon_style":"outline",
                "accent":(136,130,255)},
    "macos":   {"name":"macOS","bg":"#2b2b2d","sbg":"#353537","fg":"255,255,255","ba":0.06,
                "lbg":"#ffffff","lsbg":"#f2f1f2","lfg":"30,30,30","lba":0.08,
                "sel":"pill","sel_radius":8,"row_pad":3,"sidebar_radius":8,"icon_style":"filled",
                "accent":(0,122,255)},
    "windows": {"name":"Windows 11","bg":"#202020","sbg":"#282828","fg":"255,255,255","ba":0.04,
                "lbg":"#f9f9f9","lsbg":"#ebebeb","lfg":"0,0,0","lba":0.06,
                "sel":"win11","sel_radius":4,"row_pad":1,"sidebar_radius":4,"icon_style":"system",
                "accent":(146,146,146)},
    "minimal": {"name":"Minimal","bg":"#111114","sbg":"#0e0e11","fg":"255,255,255","ba":0.02,
                "lbg":"#ffffff","lsbg":"#fafafa","lfg":"0,0,0","lba":0.04,
                "sel":"underline","sel_radius":0,"row_pad":6,"sidebar_radius":6,"icon_style":"outline",
                "accent":(200,200,200)},
    "retro":   {"name":"Retro","bg":"#0a0a0a","sbg":"#050505","fg":"0,255,65","ba":0.08,
                "lbg":"#e8f5e9","lsbg":"#c8e6c9","lfg":"0,60,0","lba":0.06,
                "sel":"border","sel_radius":2,"row_pad":2,"sidebar_radius":2,"icon_style":"outline",
                "accent":(0,255,65)},
}

ICON_STYLES = {"system":"System","outline":"Outline","filled":"Filled","rounded":"Rounded","pack":"Icon Pack"}
ICON_PACKS_DIR = os.path.join(CFG_DIR, "icon-packs")
THEME_DESC_DIR = os.path.join(CFG_DIR, "theme-descriptions")

def load_cfg():
    try:
        with open(CFG_PATH) as f: return {**DEFAULT, **json.load(f)}
    except: return dict(DEFAULT)

def save_cfg(s):
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(CFG_PATH, 'w') as f: json.dump(s, f, indent=2)

def init_files():
    os.makedirs(CFG_DIR, exist_ok=True)
    os.makedirs(ICON_PACKS_DIR, exist_ok=True)
    # Theme descriptions
    THEME_DESC_DIR = os.path.join(CFG_DIR, "theme-descriptions")
    os.makedirs(THEME_DESC_DIR, exist_ok=True)
    defaults = {
        "nova": "Modern and vibrant. Smooth rounded corners with colorful accents and a clean layout.",
        "macos": "Inspired by macOS Finder. Pill-shaped selections, subtle sidebar, and familiar navigation.",
        "windows": "Authentic Windows 11 Explorer experience with flat sidebar and native-feeling controls.",
        "minimal": "Clean and distraction-free. Underline selections and maximum content space.",
        "retro": "Sharp borders, monospace feel. For those who appreciate a classic utilitarian aesthetic.",
    }
    for tid, desc in defaults.items():
        dp = os.path.join(THEME_DESC_DIR, f"{tid}.txt")
        if not os.path.exists(dp):
            with open(dp, "w") as f: f.write(desc)
    if not os.path.exists(CUSTOM_CSS):
        with open(CUSTOM_CSS, 'w') as f: f.write("/* Nebula Files Custom CSS - Edit & press F5 */\n")
    # Create example icon pack readme
    readme = os.path.join(ICON_PACKS_DIR, "README.txt")
    if not os.path.exists(readme):
        with open(readme, 'w') as f:
            f.write("NOVA FILES - CUSTOM ICON PACKS\n"
                    "==============================\n\n"
                    "Create a folder here with PNG or SVG icons.\n"
                    "Name icons after file types:\n\n"
                    "  folder.png    - Folders\n"
                    "  file.png      - Generic files\n"
                    "  image.png     - Images (png/jpg/gif/svg)\n"
                    "  video.png     - Videos (mp4/mkv/avi)\n"
                    "  music.png     - Audio (mp3/flac/wav)\n"
                    "  archive.png   - Archives (zip/tar/7z)\n"
                    "  code.png      - Code (py/js/c/rs)\n"
                    "  document.png  - Documents (pdf/doc)\n"
                    "  executable.png - Executables\n\n"
                    "Icon sizes: 16px, 22px, 32px, 48px, 64px recommended.\n"
                    "Any size works - they'll be scaled.\n\n"
                    "To use Windows .ico files, convert them to .png first:\n"
                    "  convert icon.ico icon.png  (ImageMagick)\n"
                    "  or use an online converter\n\n"
                    "Example folder structure:\n"
                    "  icon-packs/\n"
                    "    my-pack/\n"
                    "      folder.png\n"
                    "      file.png\n"
                    "      image.png\n"
                    "      ...\n")

def get_drives():
    drives = []
    try:
        out = subprocess.check_output(['lsblk','-Jbo','NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT,TRAN,TYPE'],text=True,stderr=subprocess.DEVNULL)
        data = json.loads(out)
        def walk(dev, ptran=""):
            tran = dev.get("tran") or ptran or ""
            for ch in dev.get("children",[]): walk(ch, tran)
            if (dev.get("type") or "") not in ("part","lvm"): return
            fs=dev.get("fstype") or ""; label=dev.get("label") or ""
            mount=dev.get("mountpoint") or ""; name=dev.get("name") or ""
            try: sz=int(dev.get("size") or 0)
            except: sz=0
            if not fs or fs=="swap" or sz<500_000_000: return
            if any(x in mount for x in ["/boot","/efi"]): return
            if any(x in label.lower() for x in ["xboot","efi","recovery"]): return
            tl=(tran or name).lower()
            tr="NVMe" if "nvme" in tl else "USB" if "usb" in tl else "SATA" if ("sata" in tl or "ata" in tl) else "SD" if "mmc" in tl else "Disk"
            ss_bytes = sz
            ss=f"{sz/1e12:.1f} TB" if sz>=1e12 else f"{sz/1e9:.1f} GB" if sz>=1e9 else f"{sz/1e6:.0f} MB"
            if not mount:
                user=os.environ.get("USER","")
                for base in [f"/run/media/{user}","/media","/mnt"]:
                    p=os.path.join(base,label) if label else ""
                    if p and os.path.exists(p) and os.path.ismount(p): mount=p; break
            # Get usage
            used_bytes = 0; total_bytes = ss_bytes
            if mount:
                try:
                    st = os.statvfs(mount)
                    total_bytes = st.f_blocks * st.f_frsize
                    used_bytes = (st.f_blocks - st.f_bfree) * st.f_frsize
                except: pass
            drives.append({"label":label or name,"size":ss,"fs":fs.upper(),"tran":tr,
                "mount":mount,"dev":f"/dev/{name}","total":total_bytes,"used":used_bytes})
        for dev in data.get("blockdevices",[]): walk(dev)
    except: pass
    return drives

def get_fonts():
    try:
        out = subprocess.check_output(['fc-list','--format','%{family}\n'],text=True,stderr=subprocess.DEVNULL)
        return ["system-ui"] + sorted(set(f.split(',')[0].strip() for f in out.strip().split('\n') if f.strip()))
    except: return ["system-ui","sans-serif","monospace"]

def fmt_bytes(b):
    if b < 1024: return f"{b} B"
    if b < 1048576: return f"{b/1024:.1f} KB"
    if b < 1073741824: return f"{b/1048576:.1f} MB"
    return f"{b/1073741824:.1f} GB"

# =========================================================
#                 CUSTOM ICON DRAWING
# =========================================================

def get_icon_packs():
    """Scan for available icon packs"""
    packs = {}
    if os.path.isdir(ICON_PACKS_DIR):
        for name in os.listdir(ICON_PACKS_DIR):
            p = os.path.join(ICON_PACKS_DIR, name)
            if os.path.isdir(p):
                # Check if it has any image files
                icons = {}
                for f in os.listdir(p):
                    base, ext = os.path.splitext(f)
                    if ext.lower() in ('.png','.svg','.xpm'):
                        icons[base.lower()] = os.path.join(p, f)
                if icons:
                    packs[name] = icons
    return packs

def draw_custom_icon(cr, x, y, sz, r, g, b, ftype, style):
    """Draw custom icon. ftype: folder/file/image/music/video/archive/code. style: outline/filled/rounded"""
    if style == "system": return False  # Use GTK icons
    dispatch = {
        ("folder","outline"): _ico_folder_outline, ("folder","filled"): _ico_folder_filled, ("folder","rounded"): _ico_folder_rounded,
        ("file","outline"): _ico_file_outline, ("file","filled"): _ico_file_filled, ("file","rounded"): _ico_file_rounded,
        ("image","outline"): _ico_img_outline, ("image","filled"): _ico_img_filled, ("image","rounded"): _ico_img_rounded,
        ("music","outline"): _ico_music_outline, ("music","filled"): _ico_music_filled, ("music","rounded"): _ico_music_rounded,
        ("video","outline"): _ico_video_outline, ("video","filled"): _ico_video_filled, ("video","rounded"): _ico_video_rounded,
        ("archive","outline"): _ico_archive_outline, ("archive","filled"): _ico_archive_filled, ("archive","rounded"): _ico_archive_rounded,
        ("code","outline"): _ico_code_outline, ("code","filled"): _ico_code_filled, ("code","rounded"): _ico_code_rounded,
    }
    fn = dispatch.get((ftype, style))
    if fn: fn(cr, x, y, sz, r, g, b); return True
    # Fallback
    fn2 = dispatch.get((ftype, "outline")) or dispatch.get(("file", style)) or _ico_file_outline
    fn2(cr, x, y, sz, r, g, b); return True

# --- FOLDER ---
def _ico_folder_outline(cr, x, y, s, r, g, b):
    lw = max(1.8, s*0.055)
    cr.set_line_width(lw); cr.set_source_rgba(r, g, b, 0.8)
    # Sharp-cornered folder outline with tab
    cr.move_to(x+s*0.1, y+s*0.22)
    cr.line_to(x+s*0.1, y+s*0.15)
    cr.line_to(x+s*0.38, y+s*0.15)
    cr.line_to(x+s*0.45, y+s*0.25)
    cr.line_to(x+s*0.9, y+s*0.25)
    cr.line_to(x+s*0.9, y+s*0.82)
    cr.line_to(x+s*0.1, y+s*0.82)
    cr.close_path(); cr.stroke()

def _ico_folder_filled(cr, x, y, s, r, g, b):
    # Solid filled folder — opaque, flat design
    # Back tab
    cr.set_source_rgba(r, g, b, 0.6)
    cr.move_to(x+s*0.1, y+s*0.2)
    cr.line_to(x+s*0.1, y+s*0.15)
    cr.line_to(x+s*0.38, y+s*0.15)
    cr.line_to(x+s*0.45, y+s*0.25)
    cr.line_to(x+s*0.9, y+s*0.25)
    cr.line_to(x+s*0.9, y+s*0.82)
    cr.line_to(x+s*0.1, y+s*0.82)
    cr.close_path(); cr.fill()
    # Front panel — brighter
    cr.set_source_rgba(r, g, b, 0.85)
    cr.rectangle(x+s*0.08, y+s*0.35, s*0.84, s*0.49); cr.fill()

def _ico_folder_rounded(cr, x, y, s, r, g, b):
    rad = s*0.08
    # Back panel with tab
    cr.set_source_rgba(r, g, b, 0.4)
    cr.new_path()
    cr.move_to(x+s*0.1+rad, y+s*0.18)
    cr.arc(x+s*0.1+rad, y+s*0.18+rad, rad, math.pi, -math.pi/2)
    cr.line_to(x+s*0.38, y+s*0.18)
    cr.line_to(x+s*0.44, y+s*0.28)
    cr.line_to(x+s*0.88-rad, y+s*0.28)
    cr.arc(x+s*0.88-rad, y+s*0.28+rad, rad, -math.pi/2, 0)
    cr.line_to(x+s*0.88, y+s*0.82-rad)
    cr.arc(x+s*0.88-rad, y+s*0.82-rad, rad, 0, math.pi/2)
    cr.line_to(x+s*0.1+rad, y+s*0.82)
    cr.arc(x+s*0.1+rad, y+s*0.82-rad, rad, math.pi/2, math.pi)
    cr.close_path(); cr.fill()
    # Front panel overlay
    cr.set_source_rgba(r, g, b, 0.6)
    _rounded_rect(cr, x+s*0.08, y+s*0.34, s*0.84, s*0.5, rad*1.2); cr.fill()

# --- FILE ---
def _ico_file_outline(cr, x, y, s, r, g, b):
    cr.set_line_width(max(1.5, s*0.06)); cr.set_source_rgba(r, g, b, 0.45)
    fold=s*0.2
    cr.move_to(x+s*0.22,y+s*0.08); cr.line_to(x+s*0.78-fold,y+s*0.08)
    cr.line_to(x+s*0.78,y+s*0.08+fold); cr.line_to(x+s*0.78,y+s*0.92)
    cr.line_to(x+s*0.22,y+s*0.92); cr.close_path(); cr.stroke()
    cr.move_to(x+s*0.78-fold,y+s*0.08); cr.line_to(x+s*0.78-fold,y+s*0.08+fold)
    cr.line_to(x+s*0.78,y+s*0.08+fold); cr.stroke()

def _ico_file_filled(cr, x, y, s, r, g, b):
    fold=s*0.18; cr.set_source_rgba(r, g, b, 0.3)
    cr.move_to(x+s*0.22,y+s*0.08); cr.line_to(x+s*0.78-fold,y+s*0.08)
    cr.line_to(x+s*0.78,y+s*0.08+fold); cr.line_to(x+s*0.78,y+s*0.92)
    cr.line_to(x+s*0.22,y+s*0.92); cr.close_path(); cr.fill()
    cr.set_source_rgba(r, g, b, 0.5)
    cr.move_to(x+s*0.78-fold,y+s*0.08); cr.line_to(x+s*0.78-fold,y+s*0.08+fold)
    cr.line_to(x+s*0.78,y+s*0.08+fold); cr.close_path(); cr.fill()
    cr.set_source_rgba(r, g, b, 0.15); cr.set_line_width(max(1,s*0.035))
    for i in range(3):
        yy=y+s*(0.4+i*0.14); cr.move_to(x+s*0.32,yy); cr.line_to(x+s*0.68,yy); cr.stroke()

def _ico_file_rounded(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r, g, b, 0.3)
    _rounded_rect(cr, x+s*0.2, y+s*0.08, s*0.6, s*0.84, s*0.08); cr.fill()

# --- IMAGE ---
def _ico_img_outline(cr, x, y, s, r, g, b):
    _ico_file_outline(cr,x,y,s,r,g,b)
    cr.set_source_rgba(r,g,b,0.4); cr.set_line_width(max(1.2,s*0.05))
    cr.move_to(x+s*0.3,y+s*0.72); cr.line_to(x+s*0.45,y+s*0.5); cr.line_to(x+s*0.55,y+s*0.6)
    cr.line_to(x+s*0.68,y+s*0.42); cr.line_to(x+s*0.72,y+s*0.72); cr.stroke()

def _ico_img_filled(cr, x, y, s, r, g, b):
    _ico_file_filled(cr,x,y,s,r,g,b)
    cr.set_source_rgba(r,g,b,0.45)
    cr.move_to(x+s*0.28,y+s*0.74); cr.line_to(x+s*0.44,y+s*0.5)
    cr.line_to(x+s*0.54,y+s*0.6); cr.line_to(x+s*0.68,y+s*0.4)
    cr.line_to(x+s*0.72,y+s*0.74); cr.close_path(); cr.fill()
    cr.arc(x+s*0.36,y+s*0.36,s*0.05,0,PI2); cr.fill()

def _ico_img_rounded(cr, x, y, s, r, g, b):
    _ico_file_rounded(cr,x,y,s,r,g,b)
    cr.set_source_rgba(r,g,b,0.5)
    cr.move_to(x+s*0.28,y+s*0.72); cr.line_to(x+s*0.44,y+s*0.48)
    cr.line_to(x+s*0.56,y+s*0.58); cr.line_to(x+s*0.7,y+s*0.38)
    cr.line_to(x+s*0.74,y+s*0.72); cr.close_path(); cr.fill()

# --- MUSIC ---
def _ico_music_outline(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r,g,b,0.5); cr.set_line_width(max(1.5,s*0.06))
    cr.arc(x+s*0.3,y+s*0.72,s*0.1,0,PI2); cr.stroke()
    cr.arc(x+s*0.7,y+s*0.65,s*0.1,0,PI2); cr.stroke()
    cr.move_to(x+s*0.4,y+s*0.72); cr.line_to(x+s*0.4,y+s*0.2); cr.stroke()
    cr.move_to(x+s*0.8,y+s*0.65); cr.line_to(x+s*0.8,y+s*0.15); cr.stroke()
    cr.move_to(x+s*0.4,y+s*0.2); cr.line_to(x+s*0.8,y+s*0.15); cr.stroke()

def _ico_music_filled(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r,g,b,0.55)
    cr.arc(x+s*0.3,y+s*0.72,s*0.12,0,PI2); cr.fill()
    cr.arc(x+s*0.7,y+s*0.65,s*0.12,0,PI2); cr.fill()
    cr.rectangle(x+s*0.38,y+s*0.18,s*0.04,s*0.56); cr.fill()
    cr.rectangle(x+s*0.78,y+s*0.13,s*0.04,s*0.54); cr.fill()
    cr.set_line_width(s*0.04); cr.move_to(x+s*0.4,y+s*0.2); cr.line_to(x+s*0.8,y+s*0.15); cr.stroke()

def _ico_music_rounded(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r,g,b,0.5)
    cr.arc(x+s*0.32,y+s*0.7,s*0.14,0,PI2); cr.fill()
    cr.arc(x+s*0.68,y+s*0.63,s*0.14,0,PI2); cr.fill()
    _rounded_rect(cr, x+s*0.39,y+s*0.16,s*0.04,s*0.56,s*0.02); cr.fill()
    _rounded_rect(cr, x+s*0.75,y+s*0.12,s*0.04,s*0.53,s*0.02); cr.fill()

# --- VIDEO ---
def _ico_video_outline(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r,g,b,0.5); cr.set_line_width(max(1.5,s*0.06))
    cr.rectangle(x+s*0.12,y+s*0.22,s*0.76,s*0.56); cr.stroke()
    cr.move_to(x+s*0.4,y+s*0.38); cr.line_to(x+s*0.4,y+s*0.62)
    cr.line_to(x+s*0.65,y+s*0.5); cr.close_path(); cr.stroke()

def _ico_video_filled(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r,g,b,0.35); cr.rectangle(x+s*0.1,y+s*0.2,s*0.8,s*0.6); cr.fill()
    cr.set_source_rgba(r,g,b,0.7)
    cr.move_to(x+s*0.38,y+s*0.35); cr.line_to(x+s*0.38,y+s*0.65)
    cr.line_to(x+s*0.68,y+s*0.5); cr.close_path(); cr.fill()

def _ico_video_rounded(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r,g,b,0.35)
    _rounded_rect(cr, x+s*0.1,y+s*0.2,s*0.8,s*0.6,s*0.1); cr.fill()
    cr.set_source_rgba(r,g,b,0.65)
    cr.move_to(x+s*0.4,y+s*0.36); cr.line_to(x+s*0.4,y+s*0.64)
    cr.line_to(x+s*0.66,y+s*0.5); cr.close_path(); cr.fill()

# --- ARCHIVE ---
def _ico_archive_outline(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r,g,b,0.45); cr.set_line_width(max(1.5,s*0.06))
    cr.rectangle(x+s*0.2,y+s*0.12,s*0.6,s*0.76); cr.stroke()
    cr.set_line_width(max(1,s*0.04))
    cr.move_to(x+s*0.45,y+s*0.12); cr.line_to(x+s*0.45,y+s*0.88); cr.stroke()
    cr.move_to(x+s*0.55,y+s*0.12); cr.line_to(x+s*0.55,y+s*0.88); cr.stroke()

def _ico_archive_filled(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r,g,b,0.3); cr.rectangle(x+s*0.2,y+s*0.12,s*0.6,s*0.76); cr.fill()
    cr.set_source_rgba(r,g,b,0.5)
    for i in range(5):
        yy = y+s*(0.18+i*0.14); col = 0.44 if i%2==0 else 0.5
        cr.rectangle(x+s*col,yy,s*0.06,s*0.1); cr.fill()

def _ico_archive_rounded(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r,g,b,0.3)
    _rounded_rect(cr, x+s*0.18,y+s*0.1,s*0.64,s*0.8,s*0.1); cr.fill()
    cr.set_source_rgba(r,g,b,0.5)
    _rounded_rect(cr, x+s*0.38,y+s*0.35,s*0.24,s*0.18,s*0.04); cr.fill()

# --- CODE ---
def _ico_code_outline(cr, x, y, s, r, g, b):
    cr.set_source_rgba(r,g,b,0.5); cr.set_line_width(max(1.5,s*0.06))
    cr.move_to(x+s*0.35,y+s*0.25); cr.line_to(x+s*0.15,y+s*0.5); cr.line_to(x+s*0.35,y+s*0.75); cr.stroke()
    cr.move_to(x+s*0.65,y+s*0.25); cr.line_to(x+s*0.85,y+s*0.5); cr.line_to(x+s*0.65,y+s*0.75); cr.stroke()
    cr.move_to(x+s*0.55,y+s*0.2); cr.line_to(x+s*0.45,y+s*0.8); cr.stroke()

def _ico_code_filled(cr, x, y, s, r, g, b):
    _ico_file_filled(cr,x,y,s,r,g,b)
    cr.set_source_rgba(r,g,b,0.6); cr.set_line_width(max(1.5,s*0.06))
    cr.move_to(x+s*0.35,y+s*0.4); cr.line_to(x+s*0.25,y+s*0.55); cr.line_to(x+s*0.35,y+s*0.7); cr.stroke()
    cr.move_to(x+s*0.65,y+s*0.4); cr.line_to(x+s*0.75,y+s*0.55); cr.line_to(x+s*0.65,y+s*0.7); cr.stroke()

def _ico_code_rounded(cr, x, y, s, r, g, b):
    _ico_file_rounded(cr,x,y,s,r,g,b)
    cr.set_source_rgba(r,g,b,0.6); cr.set_line_width(max(2,s*0.07)); cr.set_line_cap(1)
    cr.move_to(x+s*0.35,y+s*0.38); cr.line_to(x+s*0.22,y+s*0.52); cr.line_to(x+s*0.35,y+s*0.66); cr.stroke()
    cr.move_to(x+s*0.65,y+s*0.38); cr.line_to(x+s*0.78,y+s*0.52); cr.line_to(x+s*0.65,y+s*0.66); cr.stroke()

def _rounded_rect(cr, x, y, w, h, r):
    cr.new_path()
    cr.arc(x+r,y+r,r,math.pi,math.pi*1.5); cr.arc(x+w-r,y+r,r,-math.pi/2,0)
    cr.arc(x+w-r,y+h-r,r,0,math.pi/2); cr.arc(x+r,y+h-r,r,math.pi/2,math.pi)
    cr.close_path()

def get_file_type(p):
    if p.is_dir(): return "folder"
    ext = p.suffix.lower()
    if ext in ('.png','.jpg','.jpeg','.gif','.svg','.webp','.bmp','.ico'): return "image"
    if ext in ('.mp3','.flac','.wav','.ogg','.aac','.m4a'): return "music"
    if ext in ('.mp4','.mkv','.avi','.webm','.mov','.wmv'): return "video"
    if ext in ('.zip','.tar','.gz','.bz2','.xz','.7z','.rar','.deb','.rpm'): return "archive"
    if ext in ('.py','.js','.ts','.c','.cpp','.h','.rs','.go','.java','.sh','.html','.css','.json','.xml','.yaml','.toml','.lua','.rb','.php'): return "code"
    return "file"

# =========================================================
#                 APP + TAB + WINDOW
# =========================================================

class NovaApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.novafiles.app')
        self.connect('activate', lambda a: (init_files(), NovaWin(application=a).present()))

class Tab:
    def __init__(self, path=None):
        self.path = path or Path.home()
        self.hist = [self.path]; self.hi = 0
        self.sel = set(); self.sel_w = {}
        self.hidden = False; self.sort_by = "name"; self.sort_rev = False

class NovaWin(Adw.ApplicationWindow):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.set_title("Nebula Files"); self.set_default_size(1100, 750)
        self.S = load_cfg(); self.tabs = [Tab()]; self.atab = 0
        self.cloud_folders = detect_cloud_folders()
        self.vmode = "list"; self.clip = []; self.clip_cut = False
        self.drives = get_drives(); self.fonts = get_fonts()
        self.icon_packs = get_icon_packs()
        self._ttp = None; self._ttp_show = 0; self._ttp_hide = 0
        self._drag_paths = []  # v2.0.4: drag & drop state
        self._undo_stack = []  # v2.8.0: undo history
        self._redo_stack = []  # v2.8.0: redo history
        self.quick_access = load_quick_access()  # v2.8.0: user bookmarks
        self._split_active = False; self._split_focus_right = False
        self._apply_css(); self._build()
        self.nav_to(self.T.path)
        # Mount clouds in background with toast notification
        if shutil.which("rclone"):
            try:
                out = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, timeout=3)
                remotes = [r.strip() for r in out.stdout.strip().split("\n") if r.strip()]
                if remotes:
                    toast = Adw.Toast(title="☁ Connecting cloud drives...")
                    toast.set_timeout(0)
                    self._toast_overlay.add_toast(toast)
                    self._cloud_toast = toast
                    def mount_bg():
                        self._auto_mount_clouds()
                        GLib.idle_add(self._finish_cloud_mount)
                    threading.Thread(target=mount_bg, daemon=True).start()
            except: pass

    def _finish_cloud_mount(self):
        """Refresh sidebar after cloud drives mounted"""
        if hasattr(self, "_cloud_toast") and self._cloud_toast:
            self._cloud_toast.dismiss()
        self.cloud_folders = detect_cloud_folders()
        self._rebuild_full_ui(); self._load()
        count = len(self.cloud_folders)
        if count:
            toast = Adw.Toast(title=f"☁ {count} cloud drive{'s' if count > 1 else ''} connected")
            toast.set_timeout(3)
            self._toast_overlay.add_toast(toast)
        self.sbar.set_text("Ready")

    @property
    def T(self): return self.tabs[self.atab]

    def _cur_theme(self):
        return THEMES.get(self.S.get("theme","nova"), THEMES["nova"])

    def _cur_icon_style(self):
        """Get effective icon style - theme default or user override"""
        s = self.S.get("icon_style","system")
        if s == "system":
            return self._cur_theme().get("icon_style","system")
        return s

    # =========================================================
    #                 CSS
    # =========================================================

    def _apply_css(self):
        S=self.S; ar,ag,ab = S["accent_r"],S["accent_g"],S["accent_b"]
        sc=S["ui_scale"]; rh=int(S["row_height"]*sc)
        ff=S.get("font_family","system-ui"); fsz=S.get("font_size",13)
        fm=max(12,int(fsz*sc)); fs=max(10,int((fsz-1.5)*sc)); fmeta=max(10,int((fsz-1)*sc))
        th=self._cur_theme()
        display_mode = S.get("display_mode", "dark")
        # Backward compat
        if display_mode not in ("dark","blur","light"):
            display_mode = "light" if S.get("light_mode", False) else "dark"
        light = (display_mode == "light")
        blur = (display_mode == "blur")
        if light and "lbg" in th:
            bg=th["lbg"]; sbg=th["lsbg"]; fg=th["lfg"]; ba=th["lba"]
        elif blur:
            # Blur uses dark colors but with transparency
            bg=th["bg"]; sbg=th["sbg"]; fg=th["fg"]; ba=th["ba"]
        else:
            bg=th["bg"]; sbg=th["sbg"]; fg=th["fg"]; ba=th["ba"]
        sr=th["sel_radius"]; sel=th["sel"]; rpad=th["row_pad"]; sbr=th["sidebar_radius"]
        ac=f"rgba({ar},{ag},{ab}"; brd=f"rgba({fg},{ba})"
        sw=min(220,int(200*sc)); pw=min(270,int(250*sc))

        # Selection styles per theme
        if sel == "fill":
            sel_css = f".file-row.selected,.grid-item.selected {{ background: {ac},0.12); border-radius: {sr}px; }}"
            sb_sel = f".sidebar-item.active {{ background: {ac},0.14); color: {ac},0.95); border-radius: {sbr}px; }}"
        elif sel == "pill":
            sel_css = f".file-row.selected,.grid-item.selected {{ background: {ac},0.1); border-radius: 20px; }}"
            sb_sel = f".sidebar-item.active {{ background: {ac},0.12); color: {ac},0.9); border-radius: 20px; }}"
        elif sel == "win11":
            sel_css = f".file-row.selected,.grid-item.selected {{ background: {ac},0.08); border-radius: {sr}px; border: 1px solid {ac},0.15); }}"
            sb_sel = f".sidebar-item.active {{ background: {ac},0.1); color: rgba({fg},0.95); border-radius: {sbr}px; border-left: 3px solid {ac},0.85); padding-left: {int(9*sc)}px; }}"
        elif sel == "underline":
            sel_css = f".file-row.selected,.grid-item.selected {{ background: transparent; border-bottom: 2px solid {ac},0.4); border-radius: 0; }}"
            sb_sel = f".sidebar-item.active {{ background: transparent; border-bottom: 2px solid {ac},0.5); color: {ac},0.9); border-radius: 0; }}"
        elif sel == "border":
            sel_css = f".file-row.selected,.grid-item.selected {{ background: transparent; border: 1px solid {ac},0.5); border-radius: {sr}px; }}"
            sb_sel = f".sidebar-item.active {{ background: transparent; border: 1px solid {ac},0.5); color: {ac},0.95); border-radius: {sr}px; }}"
        else:
            sel_css = f".file-row.selected,.grid-item.selected {{ background: {ac},0.1); }}"
            sb_sel = f".sidebar-item.active {{ background: {ac},0.14); color: {ac},0.95); }}"

        # Blur mode — translucent glassmorphism
        blur_css = ""
        if blur:
            blur_css = f"""
        window.background {{ background: rgba(10,10,14,0.72); }}
        .nova-sidebar {{ background: rgba(0,0,0,0.30); border-right: 1px solid rgba(255,255,255,0.04); }}
        .settings-panel {{ background: rgba(0,0,0,0.25); }}
        .nova-toolbar {{ background: rgba(255,255,255,0.03); }}
        .breadcrumb {{ background: rgba(255,255,255,0.04); }}
        .addr-entry {{ background: rgba(255,255,255,0.08); border-radius: 6px; padding: 2px 8px; border: 1px solid rgba(255,255,255,0.15); font-size: {int(12*sc)}px; }}
        .addr-entry.error {{ border-color: rgba(255,80,80,0.6); }}
        .file-row {{ background: transparent; }}
        .file-row:hover {{ background: rgba(255,255,255,0.04); }}
        .sidebar-item:hover {{ background: rgba(255,255,255,0.06); }}
        .tab-bar {{ background: rgba(0,0,0,0.2); }}
        .tab-btn {{ background: rgba(255,255,255,0.04); }}
        .tab-btn.active {{ background: rgba(255,255,255,0.08); }}
        .search-entry {{ background: rgba(255,255,255,0.06); }}
        """

        # Windows 11 specific overrides
        is_win = (self.S.get("theme") == "windows")
        win_css = ""
        if is_win:
            if light:
                # === WINDOWS 11 LIGHT MODE (w11- exclusive classes) ===
                win_css = f"""
        window.background {{ background: #ffffff; }}
        .nova-tabbar {{ background: #f3f3f3; border-bottom: 1px solid rgba(0,0,0,0.05); min-height: 38px; }}
        .nova-tab {{ border-radius: 8px 8px 0 0; padding: 6px 16px; font-size: {int(12*sc)}px; font-weight: 400; color: rgba(0,0,0,0.5); background: transparent; margin: 2px 1px 0; }}
        .nova-tab:hover {{ background: rgba(0,0,0,0.03); color: rgba(0,0,0,0.7); }}
        .nova-tab.active-tab {{ background: #ffffff; color: rgba(0,0,0,0.85); }}
        .tab-close {{ color: rgba(0,0,0,0.15); }}
        .tab-close:hover {{ color: rgba(0,0,0,0.7); background: rgba(0,0,0,0.06); }}
        .tab-add {{ color: rgba(0,0,0,0.2); }}
        .tab-add:hover {{ color: rgba(0,0,0,0.5); background: rgba(0,0,0,0.04); }}
        .nova-sidebar {{ background: #f3f3f3; border-right: 1px solid rgba(0,0,0,0.05); }}
        .sidebar-item {{ border-radius: 4px; padding: {int(5*sc)}px {int(10*sc)}px; margin: 1px 6px; color: rgba(0,0,0,0.75); }}
        .sidebar-item:hover {{ background: rgba(0,0,0,0.04); }}
        .sidebar-item.active {{ background: rgba({ar},{ag},{ab},0.12); color: rgba(0,0,0,0.9); }}
        .sidebar-heading {{ font-size: {int(10*sc)}px; font-weight: 600; color: rgba(0,0,0,0.35); padding: {int(8*sc)}px 14px {int(3*sc)}px; }}
        .sidebar-icon {{ color: rgba({ar},{ag},{ab},0.6); }}
        .sidebar-item.active .sidebar-icon {{ color: rgba({ar},{ag},{ab},0.9); }}
        .sidebar-label {{ color: rgba(0,0,0,0.7); }}
        .file-row {{ padding: {int(2*sc)}px 20px; border-radius: 4px; margin: 1px 8px; min-height: {int(rh*0.9)}px; }}
        .file-row:hover {{ background: rgba(0,0,0,0.02); }}
        .file-row.selected {{ background: rgba({ar},{ag},{ab},0.08); }}
        .file-name {{ font-weight: 400; color: rgba(0,0,0,0.85); }}
        .file-meta {{ color: rgba(0,0,0,0.4); }}
        .file-icon {{ color: rgba(0,0,0,0.35); }}
        .folder-icon {{ color: rgba({ar},{ag},{ab},0.7); }}
        .col-header {{ padding: 3px 20px; background: rgba(0,0,0,0.01); border-bottom: 1px solid rgba(0,0,0,0.06); }}
        .col-header-btn {{ font-size: {int(10*sc)}px; color: rgba(0,0,0,0.4); font-weight: 500; }}
        .w11-chrome {{ background: transparent; }}
        .w11-tabbar {{ background: #ececec; border-bottom: 1px solid rgba(0,0,0,0.06); min-height: 38px; padding: 0 0 0 8px; }}
        .w11-window-controls {{ padding: 0; }}
        .w11-wc {{ min-width: 46px; min-height: 32px; border-radius: 0; color: rgba(0,0,0,0.6); padding: 0; }}
        .w11-wc:hover {{ background: rgba(0,0,0,0.05); }}
        .w11-wc-close {{ min-width: 46px; min-height: 32px; border-radius: 0; color: rgba(0,0,0,0.6); padding: 0; }}
        .w11-wc-close:hover {{ background: #e81123; color: white; }}
        .nova-tab {{ border-radius: 8px 8px 0 0; padding: 6px 16px; font-size: {int(12*sc)}px; font-weight: 400; color: rgba(0,0,0,0.5); background: transparent; margin: 4px 1px 0; }}
        .nova-tab:hover {{ background: rgba(0,0,0,0.03); color: rgba(0,0,0,0.7); }}
        .nova-tab.active-tab {{ background: #ffffff; color: rgba(0,0,0,0.85); }}
        .tab-close {{ color: rgba(0,0,0,0.15); }}
        .tab-close:hover {{ color: rgba(0,0,0,0.7); background: rgba(0,0,0,0.06); }}
        .tab-add {{ color: rgba(0,0,0,0.2); }}
        .tab-add:hover {{ color: rgba(0,0,0,0.5); background: rgba(0,0,0,0.04); }}
        .w11-sidebar {{ background: #f3f3f3; border-right: 1px solid rgba(0,0,0,0.04); }}
        .w11-sb-item {{ border-radius: 4px; padding: {int(5*sc)}px {int(12*sc)}px; margin: 1px 8px; color: rgba(0,0,0,0.75); }}
        .w11-sb-item:hover {{ background: rgba(0,0,0,0.04); }}
        .w11-sb-item.active {{ background: rgba({ar},{ag},{ab},0.1); color: rgba(0,0,0,0.9); }}
        .w11-sb-icon {{ color: rgba({ar},{ag},{ab},0.65); }}
        .w11-sb-item.active .w11-sb-icon {{ color: rgba({ar},{ag},{ab},0.95); }}
        .w11-toolbar {{ background: #f9f9f9; padding: 3px 12px; border-bottom: 1px solid rgba(0,0,0,0.04); min-height: 38px; }}
        .w11-new-btn {{ border-radius: 5px; padding: 5px 14px; color: rgba(0,0,0,0.7); font-size: {int(12*sc)}px; }}
        .w11-new-btn:hover {{ background: rgba(0,0,0,0.04); }}
        .w11-icon-btn {{ border-radius: 5px; min-width: 34px; min-height: 34px; color: rgba(0,0,0,0.45); padding: 4px; }}
        .w11-icon-btn:hover {{ background: rgba(0,0,0,0.04); color: rgba(0,0,0,0.75); }}
        .w11-text-btn {{ border-radius: 5px; padding: 5px 10px; color: rgba(0,0,0,0.5); font-size: {int(12*sc)}px; }}
        .w11-text-btn:hover {{ background: rgba(0,0,0,0.04); color: rgba(0,0,0,0.8); }}
        .w11-sep {{ opacity: 0.08; margin: 8px 4px; }}
        .w11-addr-row {{ background: #ffffff; padding: 6px 12px; border-bottom: 1px solid rgba(0,0,0,0.06); }}
        .w11-nav {{ border-radius: 5px; min-width: 32px; min-height: 32px; color: rgba(0,0,0,0.4); }}
        .w11-nav:hover {{ background: rgba(0,0,0,0.04); color: rgba(0,0,0,0.7); }}
        .w11-nav:disabled {{ color: rgba(0,0,0,0.1); }}
        .w11-addr-box {{ background: #ffffff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 4px 6px; }}
        .w11-addr-box .path-btn {{ font-size: {int(12*sc)}px; color: rgba(0,0,0,0.5); padding: 2px 4px; border-radius: 4px; background: transparent; border: none; }}
        .w11-addr-box .path-btn:hover {{ background: rgba(0,0,0,0.04); color: rgba(0,0,0,0.85); }}
        .w11-addr-box .path-current {{ color: rgba(0,0,0,0.85); font-weight: 500; }}
        .w11-addr-box .path-sep {{ color: rgba(0,0,0,0.18); font-size: {int(12*sc)}px; }}
        .w11-search {{ border-radius: 6px; background: #ffffff; border: 1px solid rgba(0,0,0,0.08); color: rgba(0,0,0,0.6); padding: 4px 10px; }}
        .w11-search:focus {{ border-color: rgba({ar},{ag},{ab},0.4); }}
        .settings-panel {{ background: #f0f0f0; border-left: 1px solid rgba(0,0,0,0.06); }}
        .settings-title {{ color: rgba(0,0,0,0.85); }}
        .settings-section {{ color: rgba(0,0,0,0.3); }}
        .settings-label {{ color: rgba(0,0,0,0.55); }}
        .settings-entry {{ background: rgba(0,0,0,0.035); border: 1px solid rgba(0,0,0,0.08); color: rgba(0,0,0,0.7); }}
        .theme-btn {{ color: rgba(0,0,0,0.5); background: rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.06); }}
        .theme-btn:hover {{ background: rgba(0,0,0,0.06); }}
        .theme-btn.active {{ background: rgba({ar},{ag},{ab},0.1); color: rgba({ar},{ag},{ab},0.9); border-color: rgba({ar},{ag},{ab},0.25); }}
        .nova-status {{ color: rgba(0,0,0,0.35); font-size: {int(11*sc)}px; }}
        .grid-item {{ border-radius: 6px; }}
        .grid-item:hover {{ background: rgba(0,0,0,0.02); }}
        .grid-name {{ color: rgba(0,0,0,0.7); }}
        .drive-card {{ background: rgba(0,0,0,0.02); border: 1px solid rgba(0,0,0,0.06); }}
        .new-menu-item {{ color: rgba(0,0,0,0.7); }}
        .new-menu-item:hover {{ background: rgba(0,0,0,0.04); }}
        .ss-panel {{ background: #f3f3f3; border-radius: 10px; padding: 14px; border: 1px solid rgba(0,0,0,0.06); }}
        scrollbar slider {{ background: rgba(0,0,0,0.06); }}
        scrollbar slider:hover {{ background: rgba(0,0,0,0.12); }}
        """
            else:
                # === WINDOWS 11 DARK MODE (w11- exclusive classes) ===
                win_css = f"""
        .nova-tabbar {{ background: #1f1f1f; border-bottom: 1px solid rgba(255,255,255,0.06); min-height: 38px; }}
        .nova-tab {{ border-radius: 8px 8px 0 0; padding: 6px 16px; font-size: {int(12*sc)}px; font-weight: 400; color: rgba(255,255,255,0.4); background: transparent; }}
        .nova-tab:hover {{ background: rgba(255,255,255,0.04); color: rgba(255,255,255,0.65); }}
        .nova-tab.active-tab {{ background: #282828; color: rgba(255,255,255,0.9); }}
        .nova-sidebar {{ background: #282828; border-right: 1px solid rgba(255,255,255,0.04); }}
        .sidebar-item {{ border-radius: 4px; padding: {int(5*sc)}px {int(10*sc)}px; margin: 1px 6px; }}
        .sidebar-item:hover {{ background: rgba(255,255,255,0.04); }}
        .sidebar-item.active {{ background: rgba({ar},{ag},{ab},0.12); }}
        .sidebar-icon {{ color: rgba({ar},{ag},{ab},0.6); }}
        .sidebar-item.active .sidebar-icon {{ color: rgba({ar},{ag},{ab},0.9); }}
        .sidebar-heading {{ font-size: {int(10*sc)}px; font-weight: 600; color: rgba(255,255,255,0.3); padding: {int(8*sc)}px 14px {int(3*sc)}px; }}
        .file-row {{ padding: {int(2*sc)}px 20px; border-radius: 4px; margin: 1px 8px; min-height: {int(rh*0.9)}px; }}
        .file-row:hover {{ background: rgba(255,255,255,0.03); }}
        .file-name {{ font-weight: 400; color: rgba(255,255,255,0.85); }}
        .file-meta {{ color: rgba(255,255,255,0.35); }}
        .col-header {{ padding: 3px 20px; background: rgba(255,255,255,0.015); border-bottom: 1px solid rgba(255,255,255,0.04); }}
        .col-header-btn {{ font-size: {int(10*sc)}px; color: rgba(255,255,255,0.35); }}
        .w11-chrome {{ background: transparent; }}
        .w11-tabbar {{ background: #1a1a1a; border-bottom: 1px solid rgba(255,255,255,0.06); min-height: 38px; padding: 0 0 0 8px; }}
        .w11-window-controls {{ padding: 0; }}
        .w11-wc {{ min-width: 46px; min-height: 32px; border-radius: 0; color: rgba(255,255,255,0.6); padding: 0; }}
        .w11-wc:hover {{ background: rgba(255,255,255,0.08); }}
        .w11-wc-close {{ min-width: 46px; min-height: 32px; border-radius: 0; color: rgba(255,255,255,0.6); padding: 0; }}
        .w11-wc-close:hover {{ background: #e81123; color: white; }}
        .nova-tab {{ border-radius: 8px 8px 0 0; padding: 6px 16px; font-size: {int(12*sc)}px; font-weight: 400; color: rgba(255,255,255,0.4); background: transparent; margin: 4px 1px 0; }}
        .nova-tab:hover {{ background: rgba(255,255,255,0.04); color: rgba(255,255,255,0.65); }}
        .nova-tab.active-tab {{ background: #282828; color: rgba(255,255,255,0.9); }}
        .w11-sidebar {{ background: #282828; border-right: 1px solid rgba(255,255,255,0.04); }}
        .w11-sb-item {{ border-radius: 4px; padding: {int(5*sc)}px {int(12*sc)}px; margin: 1px 8px; color: rgba(255,255,255,0.7); }}
        .w11-sb-item:hover {{ background: rgba(255,255,255,0.04); }}
        .w11-sb-item.active {{ background: rgba({ar},{ag},{ab},0.12); color: rgba(255,255,255,0.9); }}
        .w11-sb-icon {{ color: rgba({ar},{ag},{ab},0.6); }}
        .w11-sb-item.active .w11-sb-icon {{ color: rgba({ar},{ag},{ab},0.9); }}
        .w11-toolbar {{ background: #2d2d2d; padding: 3px 12px; border-bottom: 1px solid rgba(255,255,255,0.03); min-height: 38px; }}
        .w11-new-btn {{ border-radius: 5px; padding: 5px 14px; color: rgba(255,255,255,0.65); font-size: {int(12*sc)}px; }}
        .w11-new-btn:hover {{ background: rgba(255,255,255,0.06); }}
        .w11-icon-btn {{ border-radius: 5px; min-width: 34px; min-height: 34px; color: rgba(255,255,255,0.45); padding: 4px; }}
        .w11-icon-btn:hover {{ background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.75); }}
        .w11-text-btn {{ border-radius: 5px; padding: 5px 10px; color: rgba(255,255,255,0.45); font-size: {int(12*sc)}px; }}
        .w11-text-btn:hover {{ background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.75); }}
        .w11-sep {{ opacity: 0.06; margin: 8px 4px; }}
        .w11-addr-row {{ background: #202020; padding: 6px 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        .w11-nav {{ border-radius: 5px; min-width: 32px; min-height: 32px; color: rgba(255,255,255,0.4); }}
        .w11-nav:hover {{ background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.75); }}
        .w11-nav:disabled {{ color: rgba(255,255,255,0.1); }}
        .w11-addr-box {{ background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 4px 6px; }}
        .w11-addr-box .path-btn {{ font-size: {int(12*sc)}px; color: rgba(255,255,255,0.45); padding: 2px 4px; border-radius: 4px; background: transparent; border: none; }}
        .w11-addr-box .path-btn:hover {{ background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.85); }}
        .w11-addr-box .path-current {{ color: rgba(255,255,255,0.9); font-weight: 500; }}
        .w11-addr-box .path-sep {{ color: rgba(255,255,255,0.15); }}
        .w11-search {{ border-radius: 6px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); color: rgba(255,255,255,0.6); padding: 4px 10px; }}
        .w11-search:focus {{ border-color: rgba({ar},{ag},{ab},0.4); }}
        .settings-panel {{ background: #282828; }}
        .nova-status {{ color: rgba(255,255,255,0.35); font-size: {int(11*sc)}px; }}
        .grid-item {{ border-radius: 6px; }}
        .ss-panel {{ background: #282828; border-radius: 10px; padding: 14px; border: 1px solid rgba(255,255,255,0.06); }}
        """

        # macOS Finder specific overrides
        is_mac = (self.S.get("theme") == "macos")
        mac_css = ""
        if is_mac:
            if light:
                # === macOS FINDER LIGHT MODE ===
                mac_css = f"""
        window.background {{ background: #ffffff; }}
        .nova-tabbar {{ background: #dcdcdc; border-bottom: 1px solid rgba(0,0,0,0.1); min-height: 52px; }}
        .mac-box {{ margin: 18px 0 12px 16px; }}
        .nova-tab {{ border-radius: 6px; padding: 5px 14px; font-size: {int(12*sc)}px; font-weight: 500; color: rgba(0,0,0,0.45); background: transparent; margin: 6px 2px 6px; }}
        .nova-tab:hover {{ background: rgba(0,0,0,0.05); color: rgba(0,0,0,0.65); }}
        .nova-tab.active-tab {{ background: rgba(255,255,255,0.8); color: rgba(0,0,0,0.9); box-shadow: none; }}
        .tab-close {{ color: rgba(0,0,0,0.2); }}
        .tab-close:hover {{ color: rgba(0,0,0,0.7); background: rgba(0,0,0,0.08); }}
        .tab-add {{ color: rgba(0,0,0,0.2); }}
        .tab-add:hover {{ color: rgba(0,0,0,0.5); background: rgba(0,0,0,0.05); }}
        .nova-sidebar {{ background: #f2f1f2; border-right: 1px solid rgba(0,0,0,0.08); }}
        .sidebar-item {{ border-radius: 6px; padding: {int(4*sc)}px {int(10*sc)}px; margin: 1px 8px; color: rgba(0,0,0,0.6); }}
        .sidebar-item:hover {{ background: rgba(0,0,0,0.04); color: rgba(0,0,0,0.8); }}
        .sidebar-item.active {{ background: rgba({ar},{ag},{ab},0.12); color: rgba({ar},{ag},{ab},1.0); }}
        .sidebar-heading {{ font-size: {int(10*sc)}px; font-weight: 700; color: rgba(0,0,0,0.3); padding: {int(8*sc)}px 18px {int(3*sc)}px; }}
        .sidebar-icon {{ color: rgba(0,0,0,0.3); }}
        .sidebar-item:hover .sidebar-icon {{ color: rgba(0,0,0,0.5); }}
        .sidebar-item.active .sidebar-icon {{ color: rgba({ar},{ag},{ab},0.85); }}
        .sidebar-label {{ color: rgba(0,0,0,0.6); font-size: {int(12*sc)}px; }}
        .sidebar-meta {{ color: rgba(0,0,0,0.25); }}
        .nova-topbar {{ padding: 6px 16px 4px 14px; }}
        .file-row {{ padding: {int(3*sc)}px 20px; border-radius: 6px; margin: 1px 8px; }}
        .file-row:hover {{ background: rgba(0,0,0,0.025); }}
        .file-row.selected {{ background: rgba({ar},{ag},{ab},0.1); border-radius: 6px; }}
        .file-name {{ font-weight: 400; color: rgba(0,0,0,0.85); }}
        .file-meta {{ color: rgba(0,0,0,0.3); }}
        .file-icon {{ color: rgba(0,0,0,0.3); }}
        .folder-icon {{ color: rgba({ar},{ag},{ab},0.7); }}
        .col-header {{ padding: 3px 20px; background: transparent; border-bottom: 1px solid rgba(0,0,0,0.06); }}
        .col-header-btn {{ color: rgba(0,0,0,0.35); font-weight: 600; }}
        .nova-toolbar {{ padding: 3px 16px; background: #dcdcdc; border-bottom: 1px solid rgba(0,0,0,0.08); }}
        .tool-icon {{ border-radius: 6px; color: rgba(0,0,0,0.4); }}
        .tool-icon:hover {{ background: rgba(0,0,0,0.06); color: rgba(0,0,0,0.7); }}
        .search-bar {{ border-radius: 8px; background: rgba(0,0,0,0.05); border: none; color: rgba(0,0,0,0.6); }}
        .search-bar:focus {{ background: rgba(0,0,0,0.07); }}
        .path-btn {{ font-size: {int(12*sc)}px; color: rgba(0,0,0,0.45); padding: 2px 6px; border-radius: 4px; background: transparent; border: none; }}
        .path-btn:hover {{ color: rgba(0,0,0,0.8); background: rgba(0,0,0,0.04); }}
        .path-current {{ color: rgba(0,0,0,0.9); font-weight: 600; }}
        .path-sep {{ color: rgba(0,0,0,0.15); }}
        .nav-btn {{ border-radius: 6px; color: rgba(0,0,0,0.35); }}
        .nav-btn:hover {{ background: rgba(0,0,0,0.05); color: rgba(0,0,0,0.65); }}
        .nav-btn:disabled {{ color: rgba(0,0,0,0.1); }}
        .settings-panel {{ background: #f2f1f2; border-left: 1px solid rgba(0,0,0,0.06); }}
        .settings-title {{ color: rgba(0,0,0,0.85); }}
        .settings-section {{ color: rgba(0,0,0,0.3); }}
        .settings-label {{ color: rgba(0,0,0,0.5); }}
        .settings-entry {{ background: rgba(0,0,0,0.035); border: 1px solid rgba(0,0,0,0.08); color: rgba(0,0,0,0.7); }}
        .theme-btn {{ color: rgba(0,0,0,0.5); background: rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.06); }}
        .theme-btn:hover {{ background: rgba(0,0,0,0.06); color: rgba(0,0,0,0.75); }}
        .theme-btn.active {{ background: rgba({ar},{ag},{ab},0.1); color: rgba({ar},{ag},{ab},0.9); border-color: rgba({ar},{ag},{ab},0.25); }}
        .nova-status {{ color: rgba(0,0,0,0.3); }}
        .grid-item {{ border-radius: 8px; }}
        .grid-item:hover {{ background: rgba(0,0,0,0.025); }}
        .grid-name {{ color: rgba(0,0,0,0.7); }}
        .empty-state {{ color: rgba(0,0,0,0.12); }}
        .drive-card {{ background: rgba(0,0,0,0.02); border: 1px solid rgba(0,0,0,0.06); }}
        .nova-tooltip {{ background: #f2f1f2; border: 1px solid rgba({ar},{ag},{ab},0.2); }}
        .nova-tooltip label {{ color: rgba({ar},{ag},{ab},0.9); }}
        .new-menu-item {{ color: rgba(0,0,0,0.7); }}
        .new-menu-item:hover {{ background: rgba(0,0,0,0.04); color: rgba(0,0,0,0.9); }}
        .font-list {{ background: #f2f1f2; }}
        .font-item {{ color: rgba(0,0,0,0.6); }}
        .font-item:hover {{ background: rgba(0,0,0,0.04); }}
        scrollbar slider {{ background: rgba(0,0,0,0.06); }}
        scrollbar slider:hover {{ background: rgba(0,0,0,0.12); }}
        """
            else:
                # === macOS FINDER DARK MODE ===
                mac_css = f"""
        window.background {{ background: #2b2b2d; }}
        .nova-tabbar {{ background: #353537; border-bottom: 1px solid rgba(255,255,255,0.06); min-height: 52px; }}
        .mac-box {{ margin: 18px 0 12px 16px; }}
        .nova-tab {{ border-radius: 6px; padding: 5px 14px; font-size: {int(12*sc)}px; font-weight: 500; color: rgba(255,255,255,0.35); background: transparent; margin: 6px 2px 6px; }}
        .nova-tab:hover {{ background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.6); }}
        .nova-tab.active-tab {{ background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.9); }}
        .nova-sidebar {{ background: #353537; border-right: 1px solid rgba(255,255,255,0.05); }}
        .sidebar-item {{ border-radius: 6px; padding: {int(4*sc)}px {int(10*sc)}px; margin: 1px 8px; color: rgba(255,255,255,0.55); }}
        .sidebar-item:hover {{ background: rgba(255,255,255,0.05); color: rgba(255,255,255,0.75); }}
        .sidebar-item.active {{ background: rgba({ar},{ag},{ab},0.15); color: rgba({ar},{ag},{ab},0.95); }}
        .sidebar-heading {{ font-size: {int(10*sc)}px; font-weight: 700; color: rgba(255,255,255,0.22); }}
        .sidebar-icon {{ color: rgba(255,255,255,0.25); }}
        .sidebar-item.active .sidebar-icon {{ color: rgba({ar},{ag},{ab},0.8); }}
        .nova-topbar {{ padding: 6px 16px 4px 14px; }}
        .nova-toolbar {{ padding: 3px 16px; background: #353537; border-bottom: 1px solid rgba(255,255,255,0.06); }}
        .tool-icon {{ border-radius: 6px; color: rgba(255,255,255,0.4); }}
        .tool-icon:hover {{ background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.7); }}
        .search-bar {{ border-radius: 8px; background: rgba(255,255,255,0.06); border: none; color: rgba(255,255,255,0.6); }}
        .nav-btn {{ border-radius: 6px; color: rgba(255,255,255,0.35); }}
        .nav-btn:hover {{ background: rgba(255,255,255,0.06); }}
        .settings-panel {{ background: #353537; }}
        .grid-item {{ border-radius: 8px; }}
        """

        css = f"""
        * {{ font-family: {ff}; transition: background 150ms ease, color 150ms ease, border-color 200ms ease, opacity 200ms ease; }}
        window.background {{ background: {bg}; }}

        .nova-tabbar {{ background: {sbg}; border-bottom: 1px solid {brd}; padding: 0 8px; min-height: 36px; }}
        .mac-box {{ margin: 12px 0 8px 14px; }}
        .nova-tab {{
            border-radius: {sbr}px {sbr}px 0 0; padding: 5px 14px; margin: 4px 2px 0;
            font-size: {int(12*sc)}px; font-weight: 450; color: rgba({fg},0.4); background: transparent; border: none;
        }}
        .nova-tab:hover {{ background: rgba({fg},0.05); color: rgba({fg},0.7); }}
        .nova-tab.active-tab {{ background: {bg}; color: rgba({fg},0.85); font-weight: 550; }}
        .tab-close {{ min-width: 16px; min-height: 16px; padding: 0; margin-left: 6px; border-radius: 50%; color: rgba({fg},0.2); background: transparent; border: none; }}
        .tab-close:hover {{ color: rgba({fg},0.7); background: rgba({fg},0.1); }}
        .tab-add {{ min-width: 26px; min-height: 26px; padding: 0; margin: 5px 6px 0; border-radius: 7px; color: rgba({fg},0.25); background: transparent; border: none; }}
        .tab-add:hover {{ color: rgba({fg},0.6); background: rgba({fg},0.06); }}

        .nova-sidebar {{ background: {sbg}; border-right: 1px solid {brd}; min-width: {sw}px; }}
        .sidebar-heading {{ font-size: {int(10*sc)}px; font-weight: 600; letter-spacing: 1.5px; color: rgba({fg},0.2); padding: {int(10*sc)}px 18px {int(4*sc)}px; }}
        .sidebar-item {{ border-radius: {sbr}px; padding: {int(6*sc)}px {int(12*sc)}px; margin: 1px 8px; color: rgba({fg},0.55); }}
        .sidebar-item:hover {{ background: rgba({fg},0.05); color: rgba({fg},0.8); }}
        {sb_sel}
        .sidebar-icon {{ color: rgba({fg},0.25); }}
        .sidebar-item:hover .sidebar-icon {{ color: rgba({fg},0.5); }}
        .sidebar-item.active .sidebar-icon {{ color: {ac},0.7); }}
        .sidebar-label {{ font-size: {int(13*sc)}px; font-weight: 450; }}
        .sidebar-meta {{ font-size: {int(10*sc)}px; color: rgba({fg},0.18); }}
        .drive-type {{ font-size: {int(10*sc)}px; color: {ac},0.5); font-weight: 600; }}

        .nova-topbar {{ padding: 8px 20px 4px 16px; min-height: 30px; background: {bg}; }}
        .nav-btn {{ border-radius: {sbr}px; min-width: 28px; min-height: 28px; padding: 0; color: rgba({fg},0.3); background: transparent; border: none; }}
        .nav-btn:hover {{ background: rgba({fg},0.05); color: rgba({fg},0.7); }}
        .nav-btn:disabled {{ color: rgba({fg},0.1); }}
        .path-btn {{ border-radius: 6px; padding: 2px 7px; font-size: {int(13*sc)}px; font-weight: 450; color: rgba({fg},0.35); background: transparent; border: none; }}
        .path-btn:hover {{ color: rgba({fg},0.8); background: rgba({fg},0.04); }}
        .path-current {{ color: rgba({fg},0.85); font-weight: 600; }}
        .path-sep {{ color: rgba({fg},0.12); font-size: {int(12*sc)}px; margin: 0 2px; }}

        .nova-toolbar {{ padding: 4px 20px; background: {sbg}; border-bottom: 1px solid {brd}; min-height: 34px; }}
        .tool-icon {{ border-radius: 7px; min-width: 32px; min-height: 32px; padding: 0; color: rgba({fg},0.28); background: transparent; border: none; }}
        .tool-icon:hover {{ background: rgba({fg},0.06); color: rgba({fg},0.7); }}
        .search-bar {{ background: rgba({fg},0.04); border: 1px solid rgba({fg},0.06); border-radius: {sbr}px; padding: 0 12px; min-height: 28px; font-size: {int(12*sc)}px; color: rgba({fg},0.65); }}
        .search-bar:focus {{ border-color: {ac},0.35); background: rgba({fg},0.06); }}

        .col-header {{ padding: 4px 24px; border-bottom: 1px solid {brd}; }}
        .col-header-btn {{ font-size: {int(10*sc)}px; font-weight: 600; letter-spacing: 0.5px; color: rgba({fg},0.18); background: transparent; border: none; }}
        .col-header-btn:hover {{ color: rgba({fg},0.4); }}

        .file-row {{ padding: {rpad}px 24px; border-radius: {sr}px; margin: 1px 12px; min-height: {rh}px; }}
        .file-row:hover {{ background: rgba({fg},0.028); }}
        {sel_css}
        .file-icon {{ color: rgba({fg},0.22); }}
        .file-row:hover .file-icon {{ color: rgba({fg},0.4); }}
        .folder-icon {{ color: {ac},0.5); }}
        .file-row:hover .folder-icon {{ color: {ac},0.75); }}
        .file-name {{ font-size: {fm}px; font-weight: 420; color: rgba({fg},0.72); }}
        .file-meta {{ font-size: {fmeta}px; color: rgba({fg},0.18); }}

        .grid-item {{ border-radius: {sr+2}px; padding: 12px 8px 8px; }}
        .grid-item:hover {{ background: rgba({fg},0.028); }}
        .grid-icon {{ color: rgba({fg},0.22); }}
        .grid-folder-icon {{ color: {ac},0.5); }}
        .grid-name {{ font-size: {fs}px; font-weight: 420; color: rgba({fg},0.5); margin-top: 5px; }}

        .nova-status {{ font-size: {int(11*sc)}px; color: rgba({fg},0.16); padding: 6px 24px; }}
        .empty-state {{ color: rgba({fg},0.12); font-size: {int(14*sc)}px; }}

        .settings-panel {{ background: {sbg}; border-left: 1px solid {brd}; padding: 16px; min-width: {pw}px; }}
        .settings-title {{ font-size: {int(15*sc)}px; font-weight: 600; color: rgba({fg},0.8); margin-bottom: 12px; }}
        .settings-section {{ font-size: {int(10*sc)}px; font-weight: 600; letter-spacing: 1px; color: rgba({fg},0.22); margin-top: 12px; margin-bottom: 5px; }}
        .settings-label {{ font-size: {int(12*sc)}px; color: rgba({fg},0.5); }}
        .settings-row {{ margin-bottom: 4px; }}
        .settings-entry {{ background: rgba({fg},0.04); border: 1px solid rgba({fg},0.06); border-radius: 6px; padding: 2px 8px; min-height: 26px; font-size: {int(12*sc)}px; color: rgba({fg},0.65); }}
        .settings-entry:focus {{ border-color: {ac},0.3); }}
        .keybind-btn {{ background: rgba({fg},0.04); border: 1px solid rgba({fg},0.08); border-radius: 6px; padding: 2px 10px; font-size: {int(11*sc)}px; font-family: monospace; color: rgba({fg},0.6); }}
        .keybind-btn.recording {{ border-color: {ac},0.5); color: {ac},0.9); }}
        .apply-bar {{ background: rgba({fg},0.04); border-top: 1px solid rgba({fg},0.08); padding: 8px 4px; }}

        .theme-btn {{ border-radius: {sbr}px; padding: 4px 10px; font-size: {int(11*sc)}px; font-weight: 500; color: rgba({fg},0.4); background: rgba({fg},0.03); border: 1px solid rgba({fg},0.05); }}
        .theme-btn:hover {{ background: rgba({fg},0.07); color: rgba({fg},0.7); }}
        .theme-btn.active {{ background: {ac},0.15); color: {ac},0.9); border-color: {ac},0.3); }}
        .apply-btn {{ border-radius: 6px; padding: 4px 12px; font-size: {int(11*sc)}px; background: {ac},0.15); color: {ac},0.85); border: none; }}
        .apply-btn:hover {{ background: {ac},0.25); }}

        .nova-tooltip {{ background: {sbg}; border: 1px solid {ac},0.3); border-radius: 10px; box-shadow: 0 4px 14px rgba(0,0,0,0.3); }}
        .nova-tooltip label {{ font-size: {int(11*sc)}px; color: {ac},0.9); font-weight: 500; padding: 6px 12px; }}
        tooltip, tooltip.background {{ background: transparent; border: none; opacity: 0; min-width: 0; min-height: 0; padding: 0; }}

        .font-list {{ background: {sbg}; border: 1px solid {brd}; border-radius: 8px; }}
        .font-item {{ padding: 4px 12px; color: rgba({fg},0.6); font-size: {int(12*sc)}px; }}
        .font-item:hover {{ background: rgba({fg},0.05); color: rgba({fg},0.85); }}
        .font-item.active {{ color: {ac},0.9); font-weight: 600; }}

        .drive-card {{ background: rgba({fg},0.025); border: 1px solid {brd}; border-radius: {sr+2}px; padding: 14px 16px; margin: 4px 12px; }}
        .drive-card:hover {{ background: rgba({fg},0.04); }}
        .drive-bar-bg {{ background: rgba({fg},0.06); border-radius: 4px; min-height: 8px; }}
        .drive-bar-fill {{ border-radius: 4px; min-height: 8px; }}

        .prop-label {{ font-size: 13px; color: rgba({fg},0.45); }}
        .prop-value {{ font-size: 13px; color: rgba({fg},0.8); font-weight: 500; }}

        .ss-entry {{ background: rgba({fg},0.04); border: 2px solid {ac},0.3); border-radius: 10px; padding: 4px 14px; min-height: 34px; font-size: {int(14*sc)}px; color: rgba({fg},0.8); }}
        .ss-entry:focus {{ border-color: {ac},0.5); }}
        .ss-result {{ padding: 4px 16px; border-radius: {sr}px; margin: 1px 8px; }}
        .ss-result:hover {{ background: rgba({fg},0.04); }}
        .ss-panel {{ background: {sbg}; border-radius: 12px; padding: 16px; border: 1px solid {brd}; }}

        .new-menu-item {{ padding: 5px 14px; border-radius: {sbr}px; color: rgba({fg},0.65); font-size: {int(12*sc)}px; }}
        .new-menu-item:hover {{ background: rgba({fg},0.06); color: rgba({fg},0.9); }}
        .drop-highlight {{ background: {ac},0.1); border: 2px dashed {ac},0.35); border-radius: 8px; }}

        scrollbar slider {{ background: rgba({fg},0.05); border-radius: 100px; min-width: 4px; }}
        scrollbar slider:hover {{ background: rgba({fg},0.1); }}
        scrolledwindow viewport {{ padding: 0; margin: 0; }}
        scrolledwindow {{ padding: 0; margin: 0; }}
        {win_css}
        {mac_css}
        {blur_css}
        """.encode()

        # v2.8.3: Performance mode CSS
        perf = self.S.get("perf_mode", "normal")
        if perf == "smooth":
            perf_css = """
        * { transition: all 0.25s ease; }
        .sidebar-item { transition: background 0.2s ease, color 0.2s ease, padding 0.2s ease; }
        .sidebar-item:hover { transition: background 0.15s ease; }
        .file-row, .grid-item { transition: background 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease; }
        .file-row:hover, .grid-item:hover { transform: scale(1.01); }
        .nova-tabbar, .w11-tabbar { transition: background 0.3s ease; }
        .nova-tab, .w11-tab { transition: background 0.2s ease, opacity 0.2s ease; }
        button { transition: background 0.15s ease, color 0.15s ease, opacity 0.15s ease; }
        .settings-panel { transition: min-width 0.3s ease; }
        .qa-card { transition: background 0.2s ease, transform 0.2s ease; }
        .qa-card:hover { transform: translateY(-2px); }
        scrollbar slider { transition: background 0.2s ease; }
        """.encode()
        elif perf == "fast":
            perf_css = """
        .file-row, .grid-item, .sidebar-item, .w11-sb-item, button, .nova-tab, .w11-tab, .qa-card { transition: none; }
        .file-row:hover, .grid-item:hover { transition: none; }
        .col-header, .nova-topbar, .nova-toolbar, .w11-toolbar { transition: none; }
        revealer { transition: none; }
        scrollbar slider { transition: none; }
        """.encode()
        else:
            perf_css = b""
        css = css + perf_css

        prov = Gtk.CssProvider(); prov.load_from_data(css)
        if hasattr(self, '_cprov'):
            Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), self._cprov)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+1)
        self._cprov = prov
        if hasattr(self, '_ucprov'):
            Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), self._ucprov)
        if os.path.exists(CUSTOM_CSS):
            try:
                cp = Gtk.CssProvider(); cp.load_from_path(CUSTOM_CSS)
                Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), cp, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+2)
                self._ucprov = cp
            except: pass

    # =========================================================
    #                 TOOLTIPS
    # =========================================================
    def _tt(self, w, text):
        w.set_has_tooltip(False)
        m = Gtk.EventControllerMotion()
        m.connect("enter", lambda c,x,y: self._tt_in(w,text))
        m.connect("leave", lambda c: self._tt_out())
        w.add_controller(m)
    def _tt_in(self, w, text):
        try:
            if self._ttp_hide: GLib.source_remove(self._ttp_hide)
        except: pass
        self._ttp_hide=0
        try:
            if self._ttp_show: GLib.source_remove(self._ttp_show)
        except: pass
        self._ttp_show = GLib.timeout_add(400, self._tt_do, w, text)
    def _tt_out(self):
        try:
            if self._ttp_show: GLib.source_remove(self._ttp_show)
        except: pass
        self._ttp_show=0
        self._ttp_hide = GLib.timeout_add(50, self._tt_rm)
    def _tt_do(self, w, text):
        self._ttp_show=0; self._tt_rm()
        try:
            p=Gtk.Popover(); p.set_parent(w); p.set_autohide(False); p.set_can_focus(False)
            p.set_has_arrow(False); p.add_css_class("nova-tooltip")
            p.set_position(Gtk.PositionType.BOTTOM); p.set_child(Gtk.Label(label=text))
            p.popup(); self._ttp=p
        except: pass
        return False
    def _tt_rm(self):
        if self._ttp:
            try: self._ttp.popdown(); self._ttp.unparent()
            except: pass
            self._ttp=None
        return False

    # =========================================================
    #                 BUILD UI
    # =========================================================
    def _build(self):
        self._root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(self._root)
        handle = Gtk.WindowHandle(); handle.set_child(self._toast_overlay); self.set_content(handle)
        self._build_tabbar(self._root)
        self.cbox = Gtk.Box(); self.cbox.set_vexpand(True); self._root.append(self.cbox)
        self._build_sidebar()
        self.mbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); self.mbox.set_hexpand(True); self.cbox.append(self.mbox)
        if self._is_win():
            self._build_win11_chrome()
        else:
            self._build_topbar(); self._build_toolbar()
        self._build_colhdr()
        # Split view support
        self._split_active = False
        self._split_focus_right = False
        self.scroll = Gtk.ScrolledWindow(); self.scroll.set_vexpand(True)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_propagate_natural_height(False); self.scroll.set_hexpand(True)
        self.mbox.append(self.scroll)
        self.fc = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.fc.set_margin_top(2); self.fc.set_margin_bottom(8); self.fc.set_valign(Gtk.Align.START)
        # Force viewport alignment
        vp = Gtk.Viewport(); vp.set_child(self.fc); vp.set_vscroll_policy(Gtk.ScrollablePolicy.MINIMUM)
        self.scroll.set_child(vp)
        self.sbar = Gtk.Label(); self.sbar.set_xalign(0); self.sbar.add_css_class("nova-status"); self.mbox.append(self.sbar)
        self.srev = Gtk.Revealer(); self.srev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        perf = self.S.get("perf_mode","normal")
        if perf == "fast":
            self.srev.set_transition_duration(0)
        elif perf == "smooth":
            self.srev.set_transition_duration(350)
        self.srev.set_reveal_child(False); self._build_settings(); self.cbox.append(self.srev)
        self._build_ss(); self._keys()

    def _rebuild_full_ui(self):
        """Tear down and rebuild tabbar + sidebar + chrome when theme changes.
        This allows switching to/from Win11 which needs completely different widgets."""
        # Remove old tabbar
        if hasattr(self, '_tabbar_w') and self._tabbar_w.get_parent():
            self._root.remove(self._tabbar_w)
        # Remove old sidebar
        if hasattr(self, '_sidebar_w') and self._sidebar_w.get_parent():
            self.cbox.remove(self._sidebar_w)
        # Remove old chrome bars
        if hasattr(self, '_topbar_w') and self._topbar_w.get_parent(): self.mbox.remove(self._topbar_w)
        if hasattr(self, '_toolbar_w') and self._toolbar_w.get_parent(): self.mbox.remove(self._toolbar_w)
        # Rebuild tabbar
        self._build_tabbar(self._root)
        self._root.reorder_child_after(self._tabbar_w, None)  # tabbar first
        # Rebuild sidebar
        self._build_sidebar()
        # Rebuild chrome
        if self._is_win():
            self._build_win11_chrome()
        else:
            self._build_topbar(); self._build_toolbar()
        # Reorder mbox children: chrome before colhdr
        if hasattr(self, '_topbar_w') and self._topbar_w.get_parent():
            self.mbox.reorder_child_after(self._topbar_w, None)
        if hasattr(self, '_toolbar_w') and self._toolbar_w.get_parent():
            if hasattr(self, '_topbar_w') and self._topbar_w.get_parent():
                self.mbox.reorder_child_after(self._toolbar_w, self._topbar_w)
            else:
                self.mbox.reorder_child_after(self._toolbar_w, None)
        self.mbox.reorder_child_after(self.colhdr, self._toolbar_w)
        self._upd_bc()

    def _build_tabbar(self, p):
        if self._is_win():
            self._build_w11_tabbar(p); return
        bar = Gtk.Box(spacing=0); bar.add_css_class("nova-tabbar"); p.append(bar)
        self._tabbar_w = bar
        mac = Gtk.Box(spacing=0); mac.add_css_class("mac-box")
        for cls,tip,cb in [("close","Close",lambda b:self.close()),("min","Minimize",lambda b:self.minimize()),
            ("max","Maximize",lambda b: self.maximize() if not self.is_maximized() else self.unmaximize())]:
            cols={"close":(1.0,0.373,0.341),"min":(0.996,0.737,0.18),"max":(0.157,0.784,0.251)}
            da=Gtk.DrawingArea(); da.set_size_request(13,13); da.set_content_width(13); da.set_content_height(13)
            da.set_draw_func(lambda d,cr,w,h,c: (cr.arc(w/2,h/2,min(w,h)/2,0,PI2),cr.set_source_rgb(*c),cr.fill()), cols[cls])
            ck=Gtk.GestureClick(); ck.connect("pressed",lambda g,n,x,y,c=cb:c(None)); da.add_controller(ck)
            da.set_margin_end(8); da.set_valign(Gtk.Align.CENTER); self._tt(da,tip); mac.append(da)
        bar.append(mac)
        sep=Gtk.Separator(orientation=Gtk.Orientation.VERTICAL); sep.set_opacity(0.08); sep.set_margin_start(4); sep.set_margin_end(4); bar.append(sep)
        self.tbox=Gtk.Box(spacing=0); self.tbox.set_hexpand(True); bar.append(self.tbox)
        self._tref()

    def _build_w11_tabbar(self, p):
        """Win11 tab bar: NO traffic lights, tabs on left, window buttons on RIGHT"""
        bar = Gtk.Box(spacing=0); bar.add_css_class("w11-tabbar"); p.append(bar)
        self._tabbar_w = bar
        self.tbox = Gtk.Box(spacing=0); self.tbox.set_hexpand(True); bar.append(self.tbox)
        self._tref()
        # Window control buttons on the right (minimize, maximize, close)
        wc = Gtk.Box(spacing=0); wc.add_css_class("w11-window-controls")
        for icon, tip, cb, css in [
            ("window-minimize-symbolic","Minimize",lambda b:self.minimize(),"w11-wc"),
            ("window-maximize-symbolic","Maximize",lambda b: self.maximize() if not self.is_maximized() else self.unmaximize(),"w11-wc"),
            ("window-close-symbolic","Close",lambda b:self.close(),"w11-wc-close")]:
            b = Gtk.Button(icon_name=icon); b.add_css_class(css); b.add_css_class("flat")
            self._tt(b, tip); b.connect("clicked", cb); wc.append(b)
        bar.append(wc)

    def _tref(self):
        self._clr(self.tbox)
        for i,t in enumerate(self.tabs):
            bx=Gtk.Box(spacing=4); bx.add_css_class("nova-tab")
            if i==self.atab: bx.add_css_class("active-tab")
            # Split view: mark left/right tabs and gray inactive side
            if self._split_active and hasattr(self, '_split_left_tab') and hasattr(self, '_split_right_tab'):
                if i == self._split_left_tab:
                    bx.add_css_class("split-left")
                    if not getattr(self, '_split_focus_right', False):
                        bx.add_css_class("split-active")
                    else:
                        bx.set_opacity(0.5)
                elif i == self._split_right_tab:
                    bx.add_css_class("split-right")
                    if getattr(self, '_split_focus_right', False):
                        bx.add_css_class("split-active")
                    else:
                        bx.set_opacity(0.5)
            lb_btn = Gtk.Button(); lb_btn.add_css_class("flat"); lb_btn.set_has_frame(False)
            lb = Gtk.Label(label=t.path.name or "Filesystem")
            lb.set_ellipsize(Pango.EllipsizeMode.END); lb.set_max_width_chars(16)
            lb_btn.set_child(lb); lb_btn.connect("clicked", lambda b, idx=i: self._tswi(idx))
            bx.append(lb_btn)
            if len(self.tabs)>1:
                cl=Gtk.Button(icon_name="window-close-symbolic"); cl.add_css_class("tab-close"); cl.add_css_class("flat")
                cl.connect("clicked",lambda b,idx=i: self._tcls(idx)); bx.append(cl)
            self.tbox.append(bx)
        add=Gtk.Button(icon_name="list-add-symbolic"); add.add_css_class("tab-add"); add.add_css_class("flat")
        self._tt(add,"New Tab"); add.connect("clicked",lambda b: self._tadd()); self.tbox.append(add)

    def _tadd(self, path=None):
        self.tabs.append(Tab(path or Path.home())); self.atab=len(self.tabs)-1; self._tref(); self.nav_to(self.T.path)
    def _tcls(self, i):
        if len(self.tabs)<=1: return
        # If closing a split tab, close split view
        if self._split_active and hasattr(self, '_split_left_tab'):
            if i == self._split_left_tab or i == self._split_right_tab:
                self._toggle_split(); return
        self.tabs.pop(i)
        if self.atab>=len(self.tabs): self.atab=len(self.tabs)-1
        self._tref(); self.nav_to(self.T.path)
    def _tswi(self, i):
        # In split mode: clicking a split tab switches focus to that side
        if self._split_active and hasattr(self, '_split_left_tab') and hasattr(self, '_split_right_tab'):
            if i == self._split_left_tab:
                self._split_focus_right = False
                self.atab = i
                self._tref()
                self.nav_to(self.T.path, push=False)
                return
            elif i == self._split_right_tab:
                self._split_focus_right = True
                self.atab = i
                self._tref()
                # Don't nav_to for right - just update breadcrumb
                self._upd_bc()
                return
        self.atab=i; self._tref(); self.nav_to(self.T.path, push=False)

    # =========================================================
    #                 SIDEBAR
    # =========================================================
    def _build_sidebar(self):
        if self._is_win():
            self._build_w11_sidebar(); return
        sc=Gtk.ScrolledWindow(); sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        sc.add_css_class("nova-sidebar"); sc.set_size_request(min(220,int(200*self.S["ui_scale"])),-1); self.cbox.prepend(sc)
        self._sidebar_w = sc
        sb=Gtk.Box(orientation=Gtk.Orientation.VERTICAL); sb.set_margin_top(8); sb.set_margin_bottom(12); sc.set_child(sb)
        home=str(Path.home()); self.sb_btns={}
        h=Gtk.Label(label="PLACES"); h.set_xalign(0); h.add_css_class("sidebar-heading"); sb.append(h)
        for n,ic,p in [("Home","user-home-symbolic",home),("Documents","folder-documents-symbolic",os.path.join(home,"Documents")),
            ("Downloads","folder-download-symbolic",os.path.join(home,"Downloads")),("Music","folder-music-symbolic",os.path.join(home,"Music")),
            ("Pictures","folder-pictures-symbolic",os.path.join(home,"Pictures")),("Videos","folder-videos-symbolic",os.path.join(home,"Videos")),
            ("Games","folder-games-symbolic",os.path.join(home,"Games"))]:
            if not os.path.isdir(p) and p!=home: continue
            btn=self._mksb(n,ic,p); sb.append(btn); self.sb_btns[p]=btn
        # v2.8.0: Quick Access section
        if self.quick_access:
            self._sep(sb)
            qa_h=Gtk.Label(label="QUICK ACCESS"); qa_h.set_xalign(0); qa_h.add_css_class("sidebar-heading"); sb.append(qa_h)
            for qa in self.quick_access:
                qa_path = qa.get("path","")
                qa_name = qa.get("name", Path(qa_path).name)
                if not os.path.isdir(qa_path): continue
                qa_bx = Gtk.Box(spacing=0)
                qa_btn = self._mksb(qa_name, "folder-symbolic", qa_path)
                qa_bx.append(qa_btn); qa_btn.set_hexpand(True)
                rm_btn = Gtk.Button(icon_name="window-close-symbolic"); rm_btn.add_css_class("flat"); rm_btn.set_opacity(0.3)
                rm_btn.connect("clicked", lambda b, p=qa_path: self._remove_quick_access(p))
                qa_bx.append(rm_btn); sb.append(qa_bx); self.sb_btns[qa_path]=qa_btn
        # v2.8.0: Quick Access drop zone
        self._qa_drop_box = sb
        qa_dt = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        qa_dt.connect("drop", self._on_sidebar_qa_drop)
        sb.add_controller(qa_dt)
        self._sep(sb)
        h2=Gtk.Label(label="SYSTEM"); h2.set_xalign(0); h2.add_css_class("sidebar-heading"); sb.append(h2)
        pc_btn = Gtk.Button(); pc_btn.add_css_class("sidebar-item"); pc_btn.add_css_class("flat")
        pcbx = Gtk.Box(spacing=10)
        pcic = Gtk.Image.new_from_icon_name("computer-symbolic"); pcic.set_pixel_size(16); pcic.add_css_class("sidebar-icon"); pcbx.append(pcic)
        pclb = Gtk.Label(label="This PC"); pclb.set_xalign(0); pclb.set_hexpand(True); pclb.add_css_class("sidebar-label"); pcbx.append(pclb)
        pc_btn.set_child(pcbx); pc_btn.connect("clicked", lambda b: self._show_this_pc())
        sb.append(pc_btn); self.sb_btns["__thispc__"] = pc_btn
        trash=os.path.join(home,".local/share/Trash/files")
        trash_btn=self._mksb("Trash","user-trash-symbolic",trash); sb.append(trash_btn); self.sb_btns[trash]=trash_btn
        clr_trash=Gtk.Button(label="Clear Trash"); clr_trash.add_css_class("flat"); clr_trash.add_css_class("theme-btn")
        clr_trash.set_halign(Gtk.Align.START); clr_trash.set_margin_start(18); clr_trash.set_margin_bottom(4)
        clr_trash.connect("clicked", self._clear_trash); sb.append(clr_trash)
        for n,ic,p in [("Filesystem","drive-harddisk-symbolic","/")]:
            btn=self._mksb(n,ic,p); sb.append(btn); self.sb_btns[p]=btn
        if self.drives:
            self._sep(sb)
            h3=Gtk.Label(label="DRIVES"); h3.set_xalign(0); h3.add_css_class("sidebar-heading"); sb.append(h3)
            for d in self.drives:
                btn=self._mkdrv(d); sb.append(btn)
                if d["mount"]: self.sb_btns[d["mount"]]=btn
        # Cloud drives
        has_od = any(c["type"] == "onedrive" for c in self.cloud_folders)
        has_gd = any(c["type"] == "gdrive" for c in self.cloud_folders)
        if self.cloud_folders or not has_od or not has_gd:
            self._sep(sb)
            h4=Gtk.Label(label="CLOUD"); h4.set_xalign(0); h4.add_css_class("sidebar-heading"); sb.append(h4)
            # Show connected cloud drives with email
            for cf in self.cloud_folders:
                vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                row = Gtk.Box(spacing=0)
                btn = self._mksb(cf["name"], "network-server-symbolic", cf["path"])
                btn.set_hexpand(True); row.append(btn); self.sb_btns[cf["path"]] = btn
                add_btn = Gtk.Button(icon_name="list-add-symbolic"); add_btn.add_css_class("flat"); add_btn.set_opacity(0.4)
                add_btn.set_valign(Gtk.Align.CENTER)
                add_btn.connect("clicked", lambda b, t=cf["type"]: self._setup_cloud(t))
                row.append(add_btn); vb.append(row)
                # Show email below drive name
                email = self._get_cloud_email(cf.get("type", ""))
                if email:
                    el = Gtk.Label(label=email); el.set_xalign(0)
                    el.set_margin_start(42); el.set_opacity(0.4)
                    el.add_css_class("sidebar-meta"); el.set_ellipsize(Pango.EllipsizeMode.END)
                    el.set_max_width_chars(22); vb.append(el)
                sb.append(vb)
            # Add buttons for missing services
            if not has_od:
                row = Gtk.Box(spacing=0)
                btn=Gtk.Button(); btn.add_css_class("sidebar-item"); btn.add_css_class("flat"); btn.set_hexpand(True)
                bx=Gtk.Box(spacing=10)
                ic=Gtk.Image.new_from_icon_name("network-server-symbolic"); ic.set_pixel_size(16); ic.add_css_class("sidebar-icon"); bx.append(ic)
                lb=Gtk.Label(label="Add OneDrive"); lb.set_xalign(0); lb.set_hexpand(True); lb.add_css_class("sidebar-label"); lb.set_opacity(0.45); bx.append(lb)
                btn.set_child(bx); btn.connect("clicked", lambda b: self._setup_cloud("onedrive")); row.append(btn)
                add_btn = Gtk.Button(icon_name="list-add-symbolic"); add_btn.add_css_class("flat"); add_btn.set_opacity(0.4)
                add_btn.set_valign(Gtk.Align.CENTER)
                add_btn.connect("clicked", lambda b: self._setup_cloud("onedrive")); row.append(add_btn)
                sb.append(row)
            if not has_gd:
                row = Gtk.Box(spacing=0)
                btn=Gtk.Button(); btn.add_css_class("sidebar-item"); btn.add_css_class("flat"); btn.set_hexpand(True)
                bx=Gtk.Box(spacing=10)
                ic=Gtk.Image.new_from_icon_name("network-server-symbolic"); ic.set_pixel_size(16); ic.add_css_class("sidebar-icon"); bx.append(ic)
                lb=Gtk.Label(label="Add Google Drive"); lb.set_xalign(0); lb.set_hexpand(True); lb.add_css_class("sidebar-label"); lb.set_opacity(0.45); bx.append(lb)
                btn.set_child(bx); btn.connect("clicked", lambda b: self._setup_cloud("gdrive")); row.append(btn)
                add_btn = Gtk.Button(icon_name="list-add-symbolic"); add_btn.add_css_class("flat"); add_btn.set_opacity(0.4)
                add_btn.set_valign(Gtk.Align.CENTER)
                add_btn.connect("clicked", lambda b: self._setup_cloud("gdrive")); row.append(add_btn)
                sb.append(row)

    def _rclone_cfg_set(self, remote_name, key, value):
        """Directly write a key=value to rclone config file for a remote"""
        import re
        cfg_path = os.path.expanduser("~/.config/rclone/rclone.conf")
        try:
            with open(cfg_path) as f: text = f.read()
            # Find our section
            pattern = rf'(\[{remote_name}\][^\[]*)'
            match = re.search(pattern, text, re.DOTALL)
            if match:
                section = match.group(1)
                # Remove old key line if exists
                new_section = re.sub(rf'\n{key} = [^\n]*', '', section)
                # Add new key
                new_section = new_section.rstrip() + f"\n{key} = {value}\n"
                text = text.replace(section, new_section)
                with open(cfg_path, 'w') as f: f.write(text)
        except: pass

    def _get_cloud_email(self, service_type):
        """Get email/account info from rclone for display"""
        remote = "nova_onedrive" if service_type == "onedrive" else "nova_gdrive" if service_type == "gdrive" else None
        if not remote or not shutil.which("rclone"): return None
        try:
            # Try rclone config dump to get token info
            proc = subprocess.run(["rclone", "config", "dump"], capture_output=True, text=True, timeout=5)
            if proc.returncode != 0: return None
            import json, base64
            cfg = json.loads(proc.stdout)
            if remote not in cfg: return None
            token_str = cfg[remote].get("token", "")
            if not token_str: return None
            tok = json.loads(token_str)
            access = tok.get("access_token", "")
            if not access: return None
            # Decode JWT payload (second part)
            parts = access.split(".")
            if len(parts) < 2: return None
            # Fix padding
            payload = parts[1]
            payload += "=" * (4 - len(payload) % 4)
            try:
                data = json.loads(base64.urlsafe_b64decode(payload))
            except: return None
            # Try common email fields
            for key in ["email", "upn", "unique_name", "preferred_username"]:
                if key in data and data[key]: return data[key]
        except: pass
        return None

    def _auto_mount_clouds(self):
        """Auto-mount configured rclone remotes on startup"""
        if not shutil.which("rclone"): return
        try:
            out = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, timeout=5)
            remotes = [r.strip().rstrip(":") for r in out.stdout.strip().split("\n") if r.strip()]
        except: return
        mounts = {
            "nova_onedrive": ("OneDrive", "onedrive"),
            "nova_gdrive": ("GoogleDrive", "gdrive"),
        }
        for remote_name, (folder_name, ctype) in mounts.items():
            if remote_name not in remotes: continue
            mount_dir = os.path.join(CFG_DIR, "cloud", folder_name)
            # Skip if already mounted
            if os.path.ismount(mount_dir): continue
            try:
                if os.path.isdir(mount_dir) and os.listdir(mount_dir): continue
            except:
                # Broken FUSE mount - unmount and recreate
                try: subprocess.run(["fusermount", "-uz", mount_dir], timeout=5, capture_output=True)
                except: pass
            try: os.makedirs(mount_dir, exist_ok=True)
            except FileExistsError:
                try: subprocess.run(["fusermount", "-uz", mount_dir], timeout=5, capture_output=True)
                except: pass
            try:
                subprocess.Popen([
                    "rclone", "mount", f"{remote_name}:", mount_dir,
                    "--vfs-cache-mode", "writes",
                    "--dir-cache-time", "5m",
                    "--vfs-read-chunk-size", "8M",
                    "--daemon"
                ])
            except: pass
        # Re-detect after mounting
        import time; time.sleep(1)
        self.cloud_folders = detect_cloud_folders()

    def _setup_cloud(self, service):
        """Setup cloud drive - fully automated, no terminal needed"""
        name = "OneDrive" if service == "onedrive" else "Google Drive"
        rclone_type = "onedrive" if service == "onedrive" else "drive"
        remote_name = "nova_onedrive" if service == "onedrive" else "nova_gdrive"
        mount_dir = os.path.join(CFG_DIR, "cloud", name.replace(" ", ""))
        has_rclone = shutil.which("rclone") is not None

        if not has_rclone:
            d = Adw.MessageDialog(transient_for=self)
            d.set_heading(f"Add {name}")
            d.set_body(f"{name} requires rclone to connect.\n\nInstall with:\nsudo dnf install rclone (Fedora) or sudo apt install rclone (Ubuntu)\n\nThen try again.")
            d.add_response("ok", "OK")
            d.connect("response", lambda dlg, r: dlg.close()); d.present()
            return

        # Check if already configured
        try:
            out = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, timeout=5)
            existing = [r.strip().rstrip(":") for r in out.stdout.strip().split("\n") if r.strip()]
        except: existing = []

        if remote_name in existing:
            d = Adw.MessageDialog(transient_for=self)
            d.set_heading(f"{name}")
            d.set_body(f"{name} is already configured.\nMount it or sign in with a different account?")
            d.add_response("cancel", "Cancel")
            d.add_response("mount", "Mount Now")
            d.add_response("reconfig", "Sign In Again")
            d.set_response_appearance("mount", Adw.ResponseAppearance.SUGGESTED)
            def on_resp(dlg, resp):
                dlg.close()
                if resp == "mount": self._mount_cloud(remote_name, mount_dir, name)
                elif resp == "reconfig":
                    try: subprocess.run(["rclone", "config", "delete", remote_name], timeout=5)
                    except: pass
                    self._auto_cloud_auth(service, remote_name, rclone_type, mount_dir, name)
            d.connect("response", on_resp); d.present()
        else:
            self._auto_cloud_auth(service, remote_name, rclone_type, mount_dir, name)

    def _auto_cloud_auth(self, service, remote_name, rclone_type, mount_dir, display_name):
        """Cloud auth - Google Drive fully auto, OneDrive uses quick terminal then auto-picks drive"""
        self.sbar.set_text(f"Signing in to {display_name}... Check your browser.")

        def do_auth():
            try:
                if service == "gdrive":
                    subprocess.run(["rclone", "config", "create", remote_name, "drive",
                        "scope", "drive"], capture_output=True, timeout=10)
                    proc = subprocess.Popen(
                        ["rclone", "config", "reconnect", f"{remote_name}:", "--auto-confirm"],
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    proc.wait(timeout=120)
                    if proc.returncode == 0:
                        GLib.idle_add(self._mount_cloud, remote_name, mount_dir, display_name)
                    else:
                        msg = "Auth failed"
                        GLib.idle_add(lambda m=msg: self.sbar.set_text(f"{display_name}: {m}"))

                elif service == "onedrive":
                    # Use terminal for auth (browser needs to open), then auto-pick drive
                    GLib.idle_add(self._onedrive_auto_setup, remote_name, mount_dir, display_name)

            except Exception as ex:
                GLib.idle_add(lambda e=str(ex): self.sbar.set_text(f"Auth failed: {e}"))

        threading.Thread(target=do_auth, daemon=True).start()

    def _onedrive_auto_setup(self, remote_name, mount_dir, display_name):
        """Automated OneDrive setup using expect + auto drive fix"""
        self._od_dialog = Adw.MessageDialog(transient_for=self)
        self._od_dialog.set_heading("Connecting OneDrive")
        self._od_dialog.set_body("A small terminal will open for sign-in.\nJust sign in to Microsoft — everything else is automatic.")
        self._od_dialog.add_response("cancel", "Cancel")
        sb = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        sp = Gtk.Spinner(); sp.set_size_request(24, 24); sp.start(); sb.append(sp)
        self._od_status = Gtk.Label(label="Starting..."); sb.append(self._od_status)
        self._od_dialog.set_extra_child(sb)
        self._od_cancelled = False
        def on_cancel(dlg, resp): self._od_cancelled = True; dlg.close()
        self._od_dialog.connect("response", on_cancel)
        self._od_dialog.present()

        try: subprocess.run(["rclone", "config", "delete", remote_name], capture_output=True, timeout=5)
        except: pass

        # Write expect script that automates rclone config fully
        script = f"""#!/usr/bin/env bash
# Minimize this terminal window immediately (Wayland + X11)
(
    sleep 0.3
    gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval "global.get_window_actors().forEach(function(w){{if(w.meta_window.has_focus())w.meta_window.minimize()}})" 2>/dev/null
    xdotool getactivewindow windowminimize 2>/dev/null
) &
if command -v expect &>/dev/null; then
    expect << 'EOF'
set timeout 180
spawn rclone config
expect "*q>*"
send "n\r"
expect "*name>*"
send "{remote_name}\r"
expect "*Storage>*"
send "onedrive\r"
expect "*client_id>*"
send "\r"
expect "*client_secret>*"
send "\r"
expect "*region>*"
send "1\r"
expect "*tenant>*"
send "\r"
expect "*advanced*"
send "n\r"
expect "*web browser*"
send "y\r"
expect -timeout 180 "*config_type>*"
send "1\r"
expect -timeout 30 "*driveid>*"
sleep 1
send "3\r"
expect -timeout 30 "*y/n>*"
send "y\r"
expect -timeout 30 "*y/e/d>*"
send "y\r"
expect -timeout 10 "*q>*"
send "q\r"
expect eof
EOF
else
    echo "Installing expect..."
    echo "Please run: sudo dnf install expect"
    echo "Then try again."
    sleep 5
fi
"""
        script_path = os.path.join(CFG_DIR, "od_setup.sh")
        with open(script_path, 'w') as f: f.write(script)
        os.chmod(script_path, 0o755)

        GLib.idle_add(lambda: self._od_status.set_label("Sign in via browser..."))

        def run_hidden_expect():
            try:
                # Run expect script completely hidden - no terminal window
                proc = subprocess.Popen(
                    ["ptyxis", "--", "bash", script_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc.wait()
                if self._od_cancelled: return
                GLib.idle_add(lambda: self._od_status.set_label("Verifying..."))
                test = subprocess.run(["rclone", "lsd", f"{remote_name}:"],
                    capture_output=True, text=True, timeout=15)
                if test.returncode == 0:
                    GLib.idle_add(lambda: self._od_dialog.close())
                    GLib.idle_add(self._mount_cloud, remote_name, mount_dir, display_name)
                    return
                # Wrong drive - try fixing
                GLib.idle_add(lambda: self._od_status.set_label("Fixing drive selection..."))
                self._rclone_cfg_set(remote_name, "drive_id", "")
                try:
                    dp = subprocess.run(["rclone", "backend", "drives", f"{remote_name}:"],
                        capture_output=True, text=True, timeout=30)
                    if dp.returncode == 0:
                        import json
                        drives = json.loads(dp.stdout)
                        for d in drives:
                            did = d.get("id", "")
                            dtype = d.get("driveType", "personal")
                            self._rclone_cfg_set(remote_name, "drive_id", did)
                            self._rclone_cfg_set(remote_name, "drive_type", dtype)
                            t2 = subprocess.run(["rclone", "lsd", f"{remote_name}:"],
                                capture_output=True, text=True, timeout=15)
                            if t2.returncode == 0:
                                GLib.idle_add(lambda: self._od_dialog.close())
                                GLib.idle_add(self._mount_cloud, remote_name, mount_dir, display_name)
                                return
                except: pass
                GLib.idle_add(lambda: self._od_status.set_label("Setup failed. Try again."))
                import time; time.sleep(3)
                GLib.idle_add(lambda: self._od_dialog.close())
            except Exception as ex:
                GLib.idle_add(lambda e=str(ex): self._od_status.set_label(f"Error: {e}"))
                import time; time.sleep(3)
                GLib.idle_add(lambda: self._od_dialog.close())
        threading.Thread(target=run_hidden_expect, daemon=True).start()

    def _onedrive_pick_drive(self, remote_name, mount_dir, display_name):
        """List OneDrive drives and auto-pick the correct one"""
        self.sbar.set_text("Detecting OneDrive drives...")

        def list_drives():
            try:
                # Clear any bad drive_id first so backend commands work
                self._rclone_cfg_set(remote_name, "drive_id", "")
                self._rclone_cfg_set(remote_name, "drive_type", "personal")

                # Now list drives
                proc = subprocess.run(
                    ["rclone", "backend", "drives", f"{remote_name}:"],
                    capture_output=True, text=True, timeout=30)
                if proc.returncode == 0 and proc.stdout.strip():
                    import json
                    drives = json.loads(proc.stdout)
                    if drives:
                        GLib.idle_add(self._show_drive_picker, drives, remote_name, mount_dir, display_name)
                        return
            except: pass

            # If backend drives fails, try lsd with cleared drive_id
            test = subprocess.run(["rclone", "lsd", f"{remote_name}:"],
                capture_output=True, text=True, timeout=15)
            if test.returncode == 0:
                GLib.idle_add(self._mount_cloud, remote_name, mount_dir, display_name)
            else:
                GLib.idle_add(self._onedrive_terminal_setup, remote_name, mount_dir, display_name)

        threading.Thread(target=list_drives, daemon=True).start()

    def _show_drive_picker(self, drives, remote_name, mount_dir, display_name):
        """Show GTK dialog to pick which OneDrive drive to use"""
        # Auto-pick the actual personal OneDrive drive
        # Personal drives have short hex IDs like "3C0F07E60E4A1BF6"
        # SharePoint/metadata drives have long IDs starting with "b!"
        personal = None
        for d in drives:
            dtype = d.get("driveType", "")
            drive_id = d.get("id", "")
            name = d.get("name", "")
            # Best match: driveType is "personal"
            if dtype == "personal":
                personal = d; break
            # Second best: short hex ID (not starting with b!)
            if not drive_id.startswith("b!") and len(drive_id) < 20:
                personal = d; break
            # Third: name contains "OneDrive" or "personal"
            if "personal" in name.lower() or "onedrive" in name.lower():
                personal = d; break

        if personal:
            drive_id = personal.get("id", "")
            dtype = personal.get("driveType", "personal")
            if drive_id:
                self._rclone_cfg_set(remote_name, "drive_id", drive_id)
                self._rclone_cfg_set(remote_name, "drive_type", dtype)
            # Verify it works before mounting
            test = subprocess.run(["rclone", "lsd", f"{remote_name}:"],
                capture_output=True, text=True, timeout=15)
            if test.returncode == 0:
                self._mount_cloud(remote_name, mount_dir, display_name)
                return
            # If auto-pick failed, show picker dialog

        # Show picker dialog for user to choose
        d = Adw.MessageDialog(transient_for=self)
        d.set_heading("Select OneDrive")
        d.set_body("Which drive would you like to connect?")
        d.add_response("cancel", "Cancel")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(24); vbox.set_margin_end(24)
        selected_drive = [None]

        for i, drv in enumerate(drives):
            dtype = drv.get("driveType", "unknown")
            name = drv.get("name", f"Drive {i+1}")
            drive_id = drv.get("id", "")
            label = f"{name} ({dtype})"
            btn = Gtk.Button(label=label); btn.add_css_class("flat")
            def pick(b, did=drive_id, dt=dtype):
                selected_drive[0] = (did, dt)
                for c in list(vbox): c.remove_css_class("active-tab")
                b.add_css_class("active-tab")
            btn.connect("clicked", pick); vbox.append(btn)

        d.add_response("select", "Connect")
        d.set_response_appearance("select", Adw.ResponseAppearance.SUGGESTED)
        d.set_extra_child(vbox)

        def on_resp(dlg, resp):
            dlg.close()
            if resp == "select" and selected_drive[0]:
                did, dt = selected_drive[0]
                self._rclone_cfg_set(remote_name, "drive_id", did)
                self._rclone_cfg_set(remote_name, "drive_type", dt)
                self._mount_cloud(remote_name, mount_dir, display_name)
        d.connect("response", on_resp); d.present()

        threading.Thread(target=do_auth, daemon=True).start()

    def _onedrive_terminal_setup(self, remote_name, mount_dir, display_name):
        """OneDrive setup with clear terminal instructions"""
        self.sbar.set_text("Setting up OneDrive... Follow the terminal instructions.")
        config_script = (
            'echo ""; '
            'echo "╔══════════════════════════════════════════╗"; '
            'echo "║       Nebula Files — OneDrive Setup        ║"; '
            'echo "╚══════════════════════════════════════════╝"; '
            'echo ""; '
            'echo "A browser will open for Microsoft login."; '
            'echo "After signing in, come back here to finish."; '
            'echo ""; '
            'echo "─────────────────────────────────────────────"; '
            f'rclone config create {remote_name} onedrive 2>/dev/null; '
            f'rclone config reconnect {remote_name}: 2>&1; '
            'echo ""; '
            'echo "─────────────────────────────────────────────"; '
            'echo "✓ Setup complete! This window will close."; '
            'sleep 2'
        )
        for term_cmd in [
            ["ptyxis", "--", "bash", "-c", config_script],
            ["gnome-terminal", "--", "bash", "-c", config_script],
            ["konsole", "-e", "bash", "-c", config_script],
            ["xterm", "-e", "bash", "-c", config_script],
        ]:
            try:
                proc = subprocess.Popen(term_cmd)
                def wait_and_mount(p=proc):
                    p.wait()
                    # Verify it worked
                    try:
                        test = subprocess.run(["rclone", "lsd", f"{remote_name}:"],
                            capture_output=True, text=True, timeout=15)
                        if test.returncode == 0:
                            GLib.idle_add(self._mount_cloud, remote_name, mount_dir, display_name)
                        else:
                            GLib.idle_add(lambda: self.sbar.set_text("OneDrive setup incomplete. Try again."))
                    except:
                        GLib.idle_add(lambda: self.sbar.set_text("OneDrive setup failed."))
                threading.Thread(target=wait_and_mount, daemon=True).start()
                return
            except FileNotFoundError: continue
        self.sbar.set_text("No terminal found. Run: rclone config")

    def _onedrive_terminal_fallback(self, remote_name, mount_dir, display_name):
        """Alias for backward compat"""
        self._onedrive_terminal_setup(remote_name, mount_dir, display_name)

    def _mount_cloud(self, remote_name, mount_dir, display_name):
        """Mount rclone remote to local directory"""
        os.makedirs(mount_dir, exist_ok=True)
        # Unmount first if already mounted
        try: subprocess.run(["fusermount", "-uz", mount_dir], timeout=5, capture_output=True)
        except: pass
        def do_mount():
            try:
                self._cloud_procs = getattr(self, '_cloud_procs', [])
                proc = subprocess.Popen([
                    "rclone", "mount", f"{remote_name}:", mount_dir,
                    "--vfs-cache-mode", "writes",
                    "--dir-cache-time", "5m",
                    "--vfs-read-chunk-size", "8M",
                    "--daemon"
                ])
                self._cloud_procs.append((remote_name, mount_dir, proc))
                import time; time.sleep(2)  # Wait for mount
                if os.path.ismount(mount_dir) or os.listdir(mount_dir):
                    GLib.idle_add(self._cloud_mounted, mount_dir, display_name)
                else:
                    GLib.idle_add(lambda: self.sbar.set_text(f"Mount may still be loading... Check {mount_dir}"))
                    GLib.idle_add(self._cloud_mounted, mount_dir, display_name)
            except Exception as ex:
                GLib.idle_add(lambda e=str(ex): self.sbar.set_text(f"Mount failed: {e}"))
        threading.Thread(target=do_mount, daemon=True).start()

    def _cloud_mounted(self, mount_dir, display_name):
        """Called after cloud drive is mounted - refresh sidebar"""
        self.cloud_folders = detect_cloud_folders()
        # Add rclone mount if not already detected
        if not any(c["path"] == mount_dir for c in self.cloud_folders):
            ctype = "onedrive" if "OneDrive" in display_name else "gdrive"
            self.cloud_folders.append({"name": display_name, "path": mount_dir, "type": ctype})
        self._rebuild_full_ui(); self._load()
        self.sbar.set_text(f"{display_name} connected!")
        self.nav_to(Path(mount_dir))

    def _build_w11_sidebar(self):
        """Win11 Explorer sidebar: no section headers, flat items, tree expand for This PC"""
        sc = Gtk.ScrolledWindow(); sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.add_css_class("w11-sidebar"); sc.set_size_request(240, -1); self.cbox.prepend(sc)
        self._sidebar_w = sc
        sb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        sb.set_margin_top(8); sb.set_margin_bottom(12); sc.set_child(sb)
        home = str(Path.home()); self.sb_btns = {}
        # Quick access items — no headers, just items like real Explorer
        for n, ic, p in [("Home","user-home-symbolic",home),
            ("Desktop","user-desktop-symbolic",os.path.join(home,"Desktop")),
            ("Downloads","folder-download-symbolic",os.path.join(home,"Downloads")),
            ("Documents","folder-documents-symbolic",os.path.join(home,"Documents")),
            ("Pictures","folder-pictures-symbolic",os.path.join(home,"Pictures")),
            ("Music","folder-music-symbolic",os.path.join(home,"Music")),
            ("Videos","folder-videos-symbolic",os.path.join(home,"Videos")),
            ("Games","folder-games-symbolic",os.path.join(home,"Games"))]:
            if not os.path.isdir(p) and p != home: continue
            btn = self._mkw11sb(n, ic, p); sb.append(btn); self.sb_btns[p] = btn
        # Thin separator
        s = Gtk.Separator(); s.set_margin_top(6); s.set_margin_bottom(6); s.set_margin_start(12); s.set_margin_end(12); s.set_opacity(0.06); sb.append(s)
        # This PC with tree arrow
        pc_btn = Gtk.Button(); pc_btn.add_css_class("w11-sb-item"); pc_btn.add_css_class("flat")
        pcbx = Gtk.Box(spacing=8)
        pc_arrow = Gtk.Label(label="▾"); pc_arrow.set_opacity(0.35); pcbx.append(pc_arrow)
        pcic = Gtk.Image.new_from_icon_name("computer-symbolic"); pcic.set_pixel_size(16); pcic.add_css_class("w11-sb-icon"); pcbx.append(pcic)
        pclb = Gtk.Label(label="This PC"); pclb.set_xalign(0); pclb.set_hexpand(True); pcbx.append(pclb)
        pc_btn.set_child(pcbx); pc_btn.connect("clicked", lambda b: self._show_this_pc())
        sb.append(pc_btn); self.sb_btns["__thispc__"] = pc_btn
        # Drives indented under This PC
        if self.drives:
            for d in self.drives:
                btn = self._mkdrv(d); btn.set_margin_start(24); sb.append(btn)
                if d["mount"]: self.sb_btns[d["mount"]] = btn
        # Trash + Filesystem
        s2 = Gtk.Separator(); s2.set_margin_top(6); s2.set_margin_bottom(6); s2.set_margin_start(12); s2.set_margin_end(12); s2.set_opacity(0.06); sb.append(s2)
        trash = os.path.join(home, ".local/share/Trash/files")
        trash_btn = self._mkw11sb("Trash", "user-trash-symbolic", trash); sb.append(trash_btn); self.sb_btns[trash] = trash_btn
        fs_btn = self._mkw11sb("Filesystem", "drive-harddisk-symbolic", "/"); sb.append(fs_btn); self.sb_btns["/"] = fs_btn

    def _mkw11sb(self, name, icon, path):
        """Win11-style sidebar item — uses w11- classes, no left accent bar"""
        btn = Gtk.Button(); btn.add_css_class("w11-sb-item"); btn.add_css_class("flat")
        bx = Gtk.Box(spacing=10)
        ic = Gtk.Image.new_from_icon_name(icon); ic.set_pixel_size(16); ic.add_css_class("w11-sb-icon"); bx.append(ic)
        lb = Gtk.Label(label=name); lb.set_xalign(0); lb.set_hexpand(True); bx.append(lb)
        btn.set_child(bx); btn.connect("clicked", lambda b, p=path: self.nav_to(Path(p)))
        self._setup_drop_target(btn, Path(path))
        return btn

    def _sep(self, p):
        s=Gtk.Separator(); s.set_margin_top(8); s.set_margin_bottom(4); s.set_margin_start(18); s.set_margin_end(18); s.set_opacity(0.05); p.append(s)

    # =========================================================
    #                 QUICK ACCESS
    # =========================================================
    def _add_quick_access(self, path):
        p = str(path)
        if any(qa["path"] == p for qa in self.quick_access): return
        self.quick_access.append({"name": Path(p).name, "path": p})
        save_quick_access(self.quick_access)
        self._rebuild_full_ui(); self.sbar.set_text(f"Added to Quick Access: {Path(p).name}")

    def _remove_quick_access(self, path):
        p = str(path)
        self.quick_access = [qa for qa in self.quick_access if qa["path"] != p]
        save_quick_access(self.quick_access)
        self._rebuild_full_ui(); self.sbar.set_text("Removed from Quick Access")

    def _on_sidebar_qa_drop(self, dt, value, x, y):
        files = value.get_files() if hasattr(value, 'get_files') else []
        for f in files:
            p = Path(f.get_path())
            if p.is_dir(): self._add_quick_access(p)
        return True

    # =========================================================
    #                 UNDO / REDO
    # =========================================================
    def _record_op(self, op_type, details):
        self._undo_stack.append({"type": op_type, "items": details})
        self._redo_stack.clear()
        if len(self._undo_stack) > 50: self._undo_stack.pop(0)

    def _undo(self, b=None):
        if not self._undo_stack: self.sbar.set_text("Nothing to undo"); return
        op = self._undo_stack.pop()
        redo_items = []
        try:
            if op["type"] == "move":
                for src, dest in op["items"]:
                    if Path(dest).exists(): shutil.move(str(dest), str(src)); redo_items.append((src, dest))
            elif op["type"] == "copy":
                for src, dest in op["items"]:
                    if Path(dest).exists():
                        if Path(dest).is_dir(): shutil.rmtree(str(dest))
                        else: os.remove(str(dest))
                        redo_items.append((src, dest))
            elif op["type"] == "trash":
                for src, trash_path in op["items"]:
                    if Path(trash_path).exists(): shutil.move(str(trash_path), str(src)); redo_items.append((src, trash_path))
            elif op["type"] == "rename":
                for old_p, new_p in op["items"]:
                    if Path(new_p).exists(): os.rename(str(new_p), str(old_p)); redo_items.append((old_p, new_p))
            elif op["type"] == "new_folder":
                for _, fp in op["items"]:
                    if Path(fp).exists() and not any(Path(fp).iterdir()): os.rmdir(str(fp)); redo_items.append((_, fp))
            elif op["type"] == "new_file":
                for _, fp in op["items"]:
                    if Path(fp).exists() and Path(fp).stat().st_size == 0: os.remove(str(fp)); redo_items.append((_, fp))
            self._redo_stack.append({"type": op["type"], "items": redo_items})
            self._load(); self.sbar.set_text(f"Undone: {op['type']}")
        except Exception as ex: self.sbar.set_text(f"Undo failed: {ex}")

    def _redo(self, b=None):
        if not self._redo_stack: self.sbar.set_text("Nothing to redo"); return
        op = self._redo_stack.pop()
        undo_items = []
        try:
            if op["type"] == "move":
                for src, dest in op["items"]:
                    if Path(src).exists(): shutil.move(str(src), str(dest)); undo_items.append((src, dest))
            elif op["type"] == "copy":
                for src, dest in op["items"]:
                    if Path(src).exists():
                        if Path(src).is_dir(): shutil.copytree(str(src), str(dest))
                        else: shutil.copy2(str(src), str(dest))
                        undo_items.append((src, dest))
            elif op["type"] == "trash":
                for src, trash_path in op["items"]:
                    if Path(src).exists(): shutil.move(str(src), str(trash_path)); undo_items.append((src, trash_path))
            elif op["type"] == "rename":
                for old_p, new_p in op["items"]:
                    if Path(old_p).exists(): os.rename(str(old_p), str(new_p)); undo_items.append((old_p, new_p))
            elif op["type"] == "new_folder":
                for _, fp in op["items"]:
                    Path(fp).mkdir(exist_ok=True); undo_items.append((_, fp))
            elif op["type"] == "new_file":
                for _, fp in op["items"]:
                    Path(fp).touch(); undo_items.append((_, fp))
            self._undo_stack.append({"type": op["type"], "items": undo_items})
            self._load(); self.sbar.set_text(f"Redone: {op['type']}")
        except Exception as ex: self.sbar.set_text(f"Redo failed: {ex}")

    # =========================================================
    #                 OPEN WITH
    # =========================================================
    def _open_with(self, b=None):
        if not self.T.sel: return
        item = list(self.T.sel)[0]
        if item.is_dir(): return
        content_type = Gio.content_type_guess(str(item), None)[0]
        apps = Gio.AppInfo.get_all_for_type(content_type)
        default_app = Gio.AppInfo.get_default_for_type(content_type, False)
        d = Adw.MessageDialog(transient_for=self)
        d.set_heading("Open With"); d.set_body(f"Choose an application for {item.name}")
        d.add_response("cancel", "Cancel")
        listbox = Gtk.ListBox(); listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        listbox.add_css_class("boxed-list"); listbox.set_margin_start(24); listbox.set_margin_end(24)
        self._ow_apps = []
        for app in apps:
            row = Gtk.ListBoxRow()
            bx = Gtk.Box(spacing=12); bx.set_margin_top(6); bx.set_margin_bottom(6); bx.set_margin_start(8); bx.set_margin_end(8)
            app_icon = app.get_icon()
            if app_icon: ic = Gtk.Image.new_from_gicon(app_icon); ic.set_pixel_size(24)
            else: ic = Gtk.Image.new_from_icon_name("application-x-executable-symbolic"); ic.set_pixel_size(24)
            bx.append(ic)
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            nl = Gtk.Label(label=app.get_display_name()); nl.set_xalign(0); nl.set_hexpand(True); vb.append(nl)
            if default_app and app.get_id() == default_app.get_id():
                dl = Gtk.Label(label="Default"); dl.set_xalign(0); dl.add_css_class("sidebar-meta"); vb.append(dl)
            bx.append(vb); row.set_child(bx)
            listbox.append(row); self._ow_apps.append(app)
        sc = Gtk.ScrolledWindow(); sc.set_min_content_height(200); sc.set_max_content_height(350)
        sc.set_child(listbox); d.set_extra_child(sc)
        d.add_response("open", "Open"); d.set_response_appearance("open", Adw.ResponseAppearance.SUGGESTED)
        def on_resp(dlg, resp):
            if resp == "open":
                row = listbox.get_selected_row()
                if row:
                    idx = row.get_index()
                    if 0 <= idx < len(self._ow_apps):
                        try: self._ow_apps[idx].launch([Gio.File.new_for_path(str(item))], None)
                        except: subprocess.Popen(["xdg-open", str(item)])
            dlg.close()
        d.connect("response", on_resp); d.present()

    def _mksb(self, name, icon, path):
        btn=Gtk.Button(); btn.add_css_class("sidebar-item"); btn.add_css_class("flat")
        bx=Gtk.Box(spacing=10)
        ic=Gtk.Image.new_from_icon_name(icon); ic.set_pixel_size(16); ic.add_css_class("sidebar-icon"); bx.append(ic)
        lb=Gtk.Label(label=name); lb.set_xalign(0); lb.set_hexpand(True); lb.add_css_class("sidebar-label"); bx.append(lb)
        btn.set_child(bx); btn.connect("clicked",lambda b,p=path: self.nav_to(Path(p)))
        # v2.0.4: sidebar items accept file drops
        self._setup_drop_target(btn, Path(path))
        return btn

    def _mkdrv(self, d):
        btn=Gtk.Button(); btn.add_css_class("sidebar-item"); btn.add_css_class("flat")
        outer=Gtk.Box(spacing=10)
        ic=Gtk.Image.new_from_icon_name("drive-harddisk-symbolic"); ic.set_pixel_size(16); ic.add_css_class("sidebar-icon"); outer.append(ic)
        vb=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=1)
        nr=Gtk.Box(spacing=6)
        lb=Gtk.Label(label=d["label"]); lb.set_xalign(0); lb.add_css_class("sidebar-label"); nr.append(lb)
        tr=Gtk.Label(label=f"/ {d['tran']}"); tr.add_css_class("drive-type"); nr.append(tr)
        vb.append(nr)
        sub=Gtk.Label(label=f"{d['size']} · {d['fs']}"); sub.set_xalign(0); sub.add_css_class("sidebar-meta"); vb.append(sub)
        outer.append(vb); btn.set_child(outer)
        def on_click(b, drv=d):
            if drv["mount"] and os.path.exists(drv["mount"]): self.nav_to(Path(drv["mount"])); return
            try:
                r=subprocess.run(['udisksctl','mount','-b',drv["dev"]],capture_output=True,text=True,timeout=10)
                out = r.stdout + r.stderr
                # Find mount path in output
                for seg in out.replace("'", "`").split("`"):
                    seg = seg.strip().rstrip(".")
                    if seg.startswith("/run/") or seg.startswith("/media/"):
                        if os.path.exists(seg): self.nav_to(Path(seg)); return
            except: pass
            try:
                user=os.environ.get("USER",""); mp=f"/run/media/{user}/{drv['label']}"
                subprocess.run(['pkexec','mkdir','-p',mp],timeout=15)
                subprocess.run(['pkexec','mount',drv["dev"],mp],timeout=15)
                if os.path.exists(mp): self.nav_to(Path(mp)); return
            except: pass
            self.sbar.set_text(f"Could not mount {drv['label']}")
        btn.connect("clicked",on_click); return btn

    def _upd_sb(self):
        c=str(self.T.path)
        for p,b in self.sb_btns.items():
            if c==p: b.add_css_class("active")
            else: b.remove_css_class("active")

    # =========================================================
    #                 THIS PC VIEW
    # =========================================================
    def _show_this_pc(self):
        self._clr(self.fc); self.colhdr.set_visible(False)
        # Deselect sidebar
        for b in self.sb_btns.values(): b.remove_css_class("active")
        self.sb_btns.get("__thispc__",Gtk.Button()).add_css_class("active")
        # v2.0.4: Update breadcrumb to show "This PC"
        self._clr(self.bcrumb)
        bc=Gtk.Button(label="This PC"); bc.add_css_class("path-btn"); bc.add_css_class("flat")
        bc.add_css_class("path-current"); bc.connect("clicked", lambda b: self._show_this_pc())
        self.bcrumb.append(bc)

        S = self.S; ar,ag,ab = S["accent_r"],S["accent_g"],S["accent_b"]

        title = Gtk.Label(label="This PC"); title.set_xalign(0)
        title.set_margin_start(24); title.set_margin_top(16); title.set_margin_bottom(8)
        title.add_css_class("settings-title"); self.fc.append(title)

        # System info
        try:
            hostname = subprocess.check_output(['hostname'],text=True).strip()
            kernel = subprocess.check_output(['uname','-r'],text=True).strip()
        except: hostname="Unknown"; kernel=""
        info_lbl = Gtk.Label(label=f"{hostname}  ·  Linux {kernel}")
        info_lbl.set_xalign(0); info_lbl.set_margin_start(24); info_lbl.add_css_class("sidebar-meta")
        info_lbl.set_margin_bottom(12); self.fc.append(info_lbl)

        for d in self.drives:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.add_css_class("drive-card")

            # Header row
            hdr = Gtk.Box(spacing=12)
            ic = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic"); ic.set_pixel_size(28)
            ic.add_css_class("folder-icon"); hdr.append(ic)
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            nr = Gtk.Box(spacing=8)
            nm = Gtk.Label(label=d["label"]); nm.add_css_class("file-name"); nr.append(nm)
            tp = Gtk.Label(label=f"/ {d['tran']}"); tp.add_css_class("drive-type"); nr.append(tp)
            vb.append(nr)
            det = Gtk.Label(label=f"{d['fs']}  ·  {d['dev']}")
            det.set_xalign(0); det.add_css_class("sidebar-meta"); vb.append(det)
            hdr.append(vb)

            # Usage on right
            total = d["total"]; used = d["used"]
            is_mounted = bool(d["mount"])
            usage_vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            usage_vb.set_halign(Gtk.Align.END); usage_vb.set_hexpand(True)
            if is_mounted and total > 0:
                free = total - used
                usage_lbl = Gtk.Label(label=f"{fmt_bytes(free)} free of {fmt_bytes(total)}")
                usage_lbl.add_css_class("settings-label"); usage_vb.append(usage_lbl)
                pct = int(used*100/total)
                pct_lbl = Gtk.Label(label=f"{pct}% used")
                pct_lbl.add_css_class("sidebar-meta"); usage_vb.append(pct_lbl)
            else:
                # v2.0.4: Unmounted drives - just show total size, no fake free space
                usage_lbl = Gtk.Label(label=f"{d['size']} total")
                usage_lbl.add_css_class("settings-label"); usage_vb.append(usage_lbl)
                not_lbl = Gtk.Label(label="Not mounted")
                not_lbl.add_css_class("sidebar-meta"); usage_vb.append(not_lbl)
            hdr.append(usage_vb)
            card.append(hdr)

            # Progress bar (only for mounted drives with usage data)
            if is_mounted and total > 0:
                bar_bg = Gtk.Box(); bar_bg.add_css_class("drive-bar-bg"); bar_bg.set_size_request(-1,8)
                bar_fill = Gtk.DrawingArea()
                pct_f = min(1.0, used/total)
                bar_fill.set_size_request(int(pct_f * 600), 8)
                bar_fill.set_draw_func(self._draw_bar, (ar/255, ag/255, ab/255, pct_f))
                bar_fill.set_halign(Gtk.Align.START)
                overlay = Gtk.Overlay(); overlay.set_child(bar_bg); overlay.add_overlay(bar_fill)
                card.append(overlay)

            # Mount info
            if d["mount"]:
                mt = Gtk.Label(label=f"Mounted at: {d['mount']}")
                mt.set_xalign(0); mt.add_css_class("sidebar-meta"); card.append(mt)
            else:
                mt = Gtk.Label(label="Not mounted — click to mount")
                mt.set_xalign(0); mt.add_css_class("sidebar-meta"); card.append(mt)

            # Make card clickable
            ck = Gtk.GestureClick()
            ck.connect("pressed", lambda g,n,x,y,drv=d: self._drive_click(drv))
            card.add_controller(ck)
            self.fc.append(card)

        self.sbar.set_text(f"{len(self.drives)} drives")

    def _draw_bar(self, da, cr, w, h, data):
        r,g,b,pct = data
        if pct > 0.9: cr.set_source_rgba(0.9,0.2,0.2,0.7)  # Red when almost full
        elif pct > 0.7: cr.set_source_rgba(0.9,0.6,0.1,0.7)  # Orange
        else: cr.set_source_rgba(r,g,b,0.6)
        _rounded_rect(cr, 0, 0, w, h, 4); cr.fill()

    def _drive_click(self, drv):
        if drv["mount"] and os.path.exists(drv["mount"]):
            self.nav_to(Path(drv["mount"]))

    # =========================================================
    #                 TOPBAR + TOOLBAR
    # =========================================================
    def _is_win(self):
        return self.S.get("theme") == "windows"

    def _build_topbar(self):
        """Build address/nav bar — skipped for Win11 (handled by _build_win11_chrome)"""
        if self._is_win(): return
        tb=Gtk.Box(spacing=6); tb.add_css_class("nova-topbar"); self.mbox.append(tb)
        self._topbar_w = tb
        self.bbk=self._nbtn("go-previous-symbolic","Back",self.on_back,tb)
        self.bfw=self._nbtn("go-next-symbolic","Forward",self.on_fwd,tb)
        self._nbtn("go-up-symbolic","Up",lambda b: self.nav_to(self.T.path.parent),tb)
        self.bcrumb_wrap = Gtk.Box(spacing=0); self.bcrumb_wrap.set_hexpand(True)
        # Breadcrumb + editable address bar (click breadcrumb to edit, Esc to cancel)
        self.bcrumb = Gtk.Box(spacing=0)
        self.addr_entry = Gtk.Entry()
        self.addr_entry.set_hexpand(True); self.addr_entry.add_css_class("addr-entry")
        self.addr_entry.connect("activate", self._addr_activate)
        esc_ctrl = Gtk.EventControllerKey()
        esc_ctrl.connect("key-pressed", self._addr_key)
        self.addr_entry.add_controller(esc_ctrl)
        self.addr_entry.set_visible(False)
        self.bcrumb_wrap.append(self.bcrumb)
        self.bcrumb_wrap.append(self.addr_entry)
        # Click on breadcrumb area to enter edit mode
        click = Gtk.GestureClick(); click.connect("pressed", self._addr_edit_start)
        self.bcrumb_wrap.add_controller(click)
        tb.append(self.bcrumb_wrap)
        self.topbar_search = None
        self.bview=self._nbtn("view-grid-symbolic","Grid/List",self.on_vtog,tb)
        self.bset=Gtk.ToggleButton(icon_name="emblem-system-symbolic")
        self.bset.add_css_class("nav-btn"); self.bset.add_css_class("flat")
        self._tt(self.bset,"Settings"); self.bset.connect("toggled",lambda b: self.srev.set_reveal_child(b.get_active())); tb.append(self.bset)

    def _nbtn(self, icon, tip, cb, parent):
        b=Gtk.Button(icon_name=icon); b.add_css_class("nav-btn"); b.add_css_class("flat")
        self._tt(b,tip); b.connect("clicked",cb); parent.append(b); return b

    def _build_toolbar(self):
        """Build toolbar — skipped for Win11 (handled by _build_win11_chrome)"""
        if self._is_win(): return
        tb=Gtk.Box(spacing=2); tb.add_css_class("nova-toolbar"); self.mbox.append(tb)
        self._toolbar_w = tb
        tools=[("edit-cut-symbolic","Cut",self._cut),("edit-copy-symbolic","Copy",self._copy),
            ("edit-paste-symbolic","Paste",self._paste),None,
            ("list-add-symbolic","New ▾",self._show_new_menu),("document-edit-symbolic","Rename",self._ren),
            ("user-trash-symbolic","Delete",self._del),None,
            ("package-x-generic-symbolic","Extract",self._ext),None,
            ("edit-select-all-symbolic","Select All",self._selall),("document-properties-symbolic","Properties",self._props),
            ("utilities-terminal-symbolic","Terminal",self._term),("view-reveal-symbolic","Hidden",self._thid),
            ("funnel-symbolic","Filter",self._show_filter_menu),
            None,("view-paged-symbolic","Split View",self._toggle_split),
            None,("system-search-symbolic","Super Search",self._ss_toggle)]
        for item in tools:
            if item is None:
                s=Gtk.Separator(orientation=Gtk.Orientation.VERTICAL); s.add_css_class("tool-sep"); s.set_opacity(0.06); tb.append(s); continue
            icon,tip,cb=item
            b=Gtk.Button(icon_name=icon); b.add_css_class("tool-icon"); b.add_css_class("flat")
            self._tt(b,tip); b.connect("clicked",cb); tb.append(b)
        sp=Gtk.Box(); sp.set_hexpand(True); tb.append(sp)
        self.search=Gtk.SearchEntry(); self.search.set_placeholder_text("Search...")
        self.search.add_css_class("search-bar"); self.search.set_size_request(200,-1)
        self.search.connect("search-changed",self.on_search); tb.append(self.search)

    # =========================================================
    #       WINDOWS 11 — COMPLETELY SEPARATE UI CHROME
    # =========================================================
    def _build_win11_chrome(self):
        """Builds the entire Win11 Explorer chrome as one independent widget.
        Uses w11-* CSS classes — zero shared styling with other themes."""
        chrome = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        chrome.add_css_class("w11-chrome")
        self._toolbar_w = chrome
        self._topbar_w = Gtk.Box(); self._topbar_w.set_visible(False); self.mbox.append(self._topbar_w)

        # === ROW 1: TOOLBAR (light gray bar matching Explorer reference) ===
        row1 = Gtk.Box(spacing=0); row1.add_css_class("w11-toolbar")

        # "New ▾" button
        nb = Gtk.Button(); nb.add_css_class("w11-new-btn"); nb.add_css_class("flat")
        nbx = Gtk.Box(spacing=5); nbx.set_valign(Gtk.Align.CENTER)
        nic = Gtk.Image.new_from_icon_name("list-add-symbolic"); nic.set_pixel_size(14); nbx.append(nic)
        nlb = Gtk.Label(label="New"); nbx.append(nlb)
        narr = Gtk.Label(label="▾"); narr.set_opacity(0.4); nbx.append(narr)
        nb.set_child(nbx); nb.connect("clicked", self._show_new_menu); row1.append(nb)
        self._w11_sep(row1)

        # Icon-only action buttons
        for icon, tip, cb in [("edit-cut-symbolic","Cut",self._cut),("edit-copy-symbolic","Copy",self._copy),
            ("edit-paste-symbolic","Paste",self._paste),("document-edit-symbolic","Rename",self._ren),
            ("emblem-shared-symbolic","Share",lambda b:None),("user-trash-symbolic","Delete",self._del)]:
            b = Gtk.Button(icon_name=icon); b.add_css_class("w11-icon-btn"); b.add_css_class("flat")
            self._tt(b, tip); b.connect("clicked", cb); row1.append(b)
        self._w11_sep(row1)

        # Text dropdown buttons: Sort, View, Filter
        for label, cb in [("Sort",self._sortby_menu),("View",self.on_vtog)]:
            b = Gtk.Button(); b.add_css_class("w11-text-btn"); b.add_css_class("flat")
            bx = Gtk.Box(spacing=3); bx.set_valign(Gtk.Align.CENTER)
            lb = Gtk.Label(label=label); bx.append(lb)
            arr = Gtk.Label(label="▾"); arr.set_opacity(0.35); bx.append(arr)
            b.set_child(bx); b.connect("clicked", cb); row1.append(b)
        # Filter button with popover
        fb = Gtk.Button(); fb.add_css_class("w11-text-btn"); fb.add_css_class("flat")
        fbx = Gtk.Box(spacing=3); fbx.set_valign(Gtk.Align.CENTER)
        fbx.append(Gtk.Label(label="Filter"))
        farr = Gtk.Label(label="▾"); farr.set_opacity(0.35); fbx.append(farr)
        fb.set_child(fbx); fb.connect("clicked", self._show_filter_menu); row1.append(fb)
        self._w11_sep(row1)

        # "···" overflow opens settings
        more = Gtk.Button(label="···"); more.add_css_class("w11-text-btn"); more.add_css_class("flat")
        row1.append(more)
        chrome.append(row1)

        # === ROW 2: ADDRESS BAR (white row with bordered address + search boxes) ===
        row2 = Gtk.Box(spacing=8); row2.add_css_class("w11-addr-row")

        # Nav buttons: ← → ↑
        self.bbk = Gtk.Button(icon_name="go-previous-symbolic"); self.bbk.add_css_class("w11-nav"); self.bbk.add_css_class("flat")
        self.bbk.connect("clicked", self.on_back); row2.append(self.bbk)
        self.bfw = Gtk.Button(icon_name="go-next-symbolic"); self.bfw.add_css_class("w11-nav"); self.bfw.add_css_class("flat")
        self.bfw.connect("clicked", self.on_fwd); row2.append(self.bfw)
        up_btn = Gtk.Button(icon_name="go-up-symbolic"); up_btn.add_css_class("w11-nav"); up_btn.add_css_class("flat")
        up_btn.connect("clicked", lambda b: self.nav_to(self.T.path.parent)); row2.append(up_btn)

        # Address box (bordered rounded container with home icon + breadcrumbs)
        self.bcrumb_wrap = Gtk.Box(spacing=0); self.bcrumb_wrap.add_css_class("w11-addr-box")
        self.bcrumb_wrap.set_hexpand(True)
        home_ic = Gtk.Image.new_from_icon_name("user-home-symbolic"); home_ic.set_pixel_size(14)
        home_ic.set_margin_start(6); home_ic.set_margin_end(2); home_ic.set_opacity(0.5)
        self.bcrumb_wrap.append(home_ic)
        self.bcrumb = Gtk.Box(spacing=0); self.bcrumb_wrap.append(self.bcrumb)
        row2.append(self.bcrumb_wrap)

        # Search box (separate bordered box on the right)
        self.topbar_search = Gtk.SearchEntry(); self.topbar_search.add_css_class("w11-search")
        self.topbar_search.set_placeholder_text("Search Home"); self.topbar_search.set_size_request(200, -1)
        self.topbar_search.connect("search-changed", self.on_search); row2.append(self.topbar_search)

        chrome.append(row2)
        self.mbox.append(chrome)

        # Settings toggle — connected to the "···" overflow button
        self.bset = Gtk.ToggleButton()
        self.bset.set_visible(False)
        self.bset.connect("toggled", lambda b: self.srev.set_reveal_child(b.get_active()))
        # Wire "···" to toggle settings panel
        more.connect("clicked", lambda b: self.bset.set_active(not self.bset.get_active()))
        self.search = None

    def _w11_sep(self, parent):
        s = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL); s.add_css_class("w11-sep"); parent.append(s)

    # =========================================================
    #                 NEW / SORT MENUS
    # =========================================================
    def _show_new_menu(self, b):
        pop = Gtk.Popover(); pop.set_parent(b); pop.set_has_arrow(False)
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vb.set_margin_top(6); vb.set_margin_bottom(6); vb.set_margin_start(4); vb.set_margin_end(4)
        items = [
            ("folder-new-symbolic", "New Folder", lambda _: self._newfld(None)),
            ("text-x-generic-symbolic", "New Text File", lambda _: self._new_file("Untitled.txt")),
            ("text-x-script-symbolic", "New Python File", lambda _: self._new_file("script.py")),
            ("text-html-symbolic", "New HTML File", lambda _: self._new_file("index.html")),
            ("text-x-script-symbolic", "New Shell Script", lambda _: self._new_file("script.sh")),
            ("x-office-document-symbolic", "New Markdown", lambda _: self._new_file("document.md")),
        ]
        for icon, label, cb in items:
            btn = Gtk.Button(); btn.add_css_class("flat"); btn.add_css_class("new-menu-item")
            bx = Gtk.Box(spacing=8)
            ic = Gtk.Image.new_from_icon_name(icon); ic.set_pixel_size(16); bx.append(ic)
            lb = Gtk.Label(label=label); lb.set_xalign(0); bx.append(lb)
            btn.set_child(bx)
            def on_click(b, callback=cb): pop.popdown(); callback(b)
            btn.connect("clicked", on_click); vb.append(btn)
        pop.set_child(vb); pop.popup()

    def _new_file(self, default_name):
        d=Adw.MessageDialog(transient_for=self); d.set_heading("New File"); d.set_body("File name:")
        d.add_response("cancel","Cancel"); d.add_response("create","Create")
        d.set_response_appearance("create",Adw.ResponseAppearance.SUGGESTED)
        e=Gtk.Entry(); e.set_text(default_name); e.set_margin_start(24); e.set_margin_end(24); d.set_extra_child(e)
        def on_resp(dlg, r, ent):
            if r=="create":
                name = ent.get_text().strip()
                if name:
                    fp = self.T.path / name
                    if not fp.exists():
                        try:
                            fp.touch(); self._record_op("new_file", [("", str(fp))]); self._load()
                        except: self.sbar.set_text(f"Could not create {name}")
                    else: self.sbar.set_text(f"{name} already exists")
            dlg.close()
        d.connect("response", on_resp, e); d.present()

    def _sortby_menu(self, b):
        pop = Gtk.Popover(); pop.set_parent(b); pop.set_has_arrow(False)
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vb.set_margin_top(6); vb.set_margin_bottom(6); vb.set_margin_start(4); vb.set_margin_end(4)
        for label, key in [("Name", "name"), ("Date modified", "modified"), ("Size", "size"), ("Type", "type")]:
            btn = Gtk.Button(label=label); btn.add_css_class("flat"); btn.add_css_class("new-menu-item")
            def on_click(b, k=key): pop.popdown(); self._sortby(k)
            btn.connect("clicked", on_click); vb.append(btn)
        pop.set_child(vb); pop.popup()

    def _build_colhdr(self):
        self.colhdr=Gtk.Box(); self.colhdr.add_css_class("col-header"); self.mbox.append(self.colhdr)
        for l,k,exp,w in [("NAME","name",True,-1),("MODIFIED","modified",False,170),("SIZE","size",False,90)]:
            b=Gtk.Button(label=l); b.add_css_class("col-header-btn"); b.add_css_class("flat")
            if exp: b.set_hexpand(True); b.set_halign(Gtk.Align.START)
            elif w>0: b.set_size_request(w,-1); b.set_halign(Gtk.Align.END)
            b.connect("clicked",lambda _,k=k: self._sortby(k)); self.colhdr.append(b)

    # =========================================================
    #                 DRAG & DROP (v2.0.4)
    # =========================================================
    def _setup_drag_source(self, widget, entry):
        """Make a file row/grid item draggable — uses file URIs for cross-app compatibility"""
        drag = Gtk.DragSource()
        drag.set_actions(Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        def on_prepare(src, x, y):
            if entry in self.T.sel and len(self.T.sel) > 1:
                self._drag_paths = [str(e) for e in self.T.sel]
            else:
                self._drag_paths = [str(entry)]
            # Send both plain paths (for internal) and file URIs (for external apps)
            uris = ["file://" + urllib.parse.quote(p) for p in self._drag_paths]
            uri_str = "\n".join(uris)
            path_str = "\n".join(self._drag_paths)
            # Create providers for both formats
            providers = []
            # File list as Gio.File objects (best for cross-app)
            files = [Gio.File.new_for_path(p) for p in self._drag_paths]
            file_val = GObject.Value(Gio.File, files[0]) if len(files) == 1 else None
            # text/uri-list for other apps
            uri_val = GObject.Value(str, uri_str)
            providers.append(Gdk.ContentProvider.new_for_value(uri_val))
            # Also plain text paths for internal use
            if file_val:
                try: providers.append(Gdk.ContentProvider.new_for_value(file_val))
                except: pass
            if len(providers) > 1:
                return Gdk.ContentProvider.new_union(providers)
            return providers[0]
        def on_begin(src, drag_obj):
            cnt = len(self._drag_paths)
            label = f"{cnt} items" if cnt > 1 else Path(self._drag_paths[0]).name
            snap = Gtk.DragIcon.get_for_drag(drag_obj)
            lbl = Gtk.Label(label=f"  {label}  "); lbl.add_css_class("file-name")
            snap.set_child(lbl)
        drag.connect("prepare", on_prepare)
        drag.connect("drag-begin", on_begin)
        widget.add_controller(drag)

    def _setup_drop_target(self, widget, dest_path=None):
        """Make a widget accept file drops (folders in file list, sidebar items)"""
        drop = Gtk.DropTarget.new(str, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        def on_enter(target, x, y):
            widget.add_css_class("drop-highlight")
            return Gdk.DragAction.MOVE
        def on_leave(target):
            widget.remove_css_class("drop-highlight")
        def on_drop(target, value, x, y):
            widget.remove_css_class("drop-highlight")
            actual_dest = dest_path if dest_path else self.T.path
            if not actual_dest.exists() or not actual_dest.is_dir(): return False
            paths = value.split("\n")
            moved = 0
            for ps in paths:
                ps = ps.strip()
                if not ps: continue
                # Handle file:// URIs from external apps
                if ps.startswith("file://"):
                    ps = urllib.parse.unquote(ps[7:])
                src = Path(ps)
                if not src.exists(): continue
                if src == actual_dest or src.parent == actual_dest: continue
                dst = actual_dest / src.name
                if dst.exists():
                    base, ext = dst.stem, dst.suffix; i=1
                    while dst.exists(): dst = actual_dest / f"{base} ({i}){ext}"; i+=1
                try: shutil.move(str(src), str(dst)); moved += 1
                except: pass
            if moved:
                self._load()
                if self._split_active and hasattr(self, '_split_fc2'):
                    self._load_split_right()
                self.sbar.set_text(f"Moved {moved} item{'s' if moved>1 else ''}")
            return True
        drop.connect("enter", on_enter)
        drop.connect("leave", on_leave)
        drop.connect("drop", on_drop)
        widget.add_controller(drop)

    # =========================================================
    #                 SUPER SEARCH
    # =========================================================
    def _build_ss(self):
        self.ss_rev=Gtk.Revealer()
        perf = self.S.get("perf_mode","normal")
        if perf == "fast":
            self.ss_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
            self.ss_rev.set_transition_duration(0)
        elif perf == "smooth":
            self.ss_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
            self.ss_rev.set_transition_duration(350)
        else:
            self.ss_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.ss_rev.set_reveal_child(False); self.ss_rev.set_valign(Gtk.Align.START)
        vb=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        vb.add_css_class("ss-panel")  # v2.1.0: distinct background for search results
        vb.set_margin_start(60); vb.set_margin_end(60); vb.set_margin_top(12); vb.set_margin_bottom(12)
        self.ss_e=Gtk.Entry(); self.ss_e.set_placeholder_text("Search everywhere...")
        self.ss_e.add_css_class("ss-entry"); self.ss_e.connect("activate",self._ss_run); vb.append(self.ss_e)
        self.ss_sc=Gtk.ScrolledWindow(); self.ss_sc.set_max_content_height(400)
        self.ss_sc.set_propagate_natural_height(True); self.ss_sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        self.ss_res=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=2); self.ss_sc.set_child(self.ss_res)
        vb.append(self.ss_sc); self.ss_rev.set_child(vb)
        self.mbox.insert_child_after(self.ss_rev, self.colhdr)

    def _ss_toggle(self, b=None):
        vis=not self.ss_rev.get_reveal_child(); self.ss_rev.set_reveal_child(vis)
        if vis: self.ss_e.grab_focus()

    def _ss_run(self, e):
        q=e.get_text().strip()
        if not q: return
        self._clr(self.ss_res); self.sbar.set_text("Searching...")
        perf = self.S.get("perf_mode","normal")
        def go():
            results=[]
            if perf == "fast":
                # Fast: try locate first (indexed, instant), then shallow find as fallback
                try:
                    out=subprocess.run(['locate','-i','-l','40',q],capture_output=True,text=True,timeout=2)
                    results=out.stdout.strip().split('\n')[:40]
                except:
                    try:
                        cmd=['find',str(Path.home()),'-maxdepth','3','-iname',f'*{q}*','-not','-path','*/.*']
                        out=subprocess.run(cmd,capture_output=True,text=True,timeout=3)
                        results=out.stdout.strip().split('\n')[:30]
                    except: pass
            else:
                try:
                    cmd=['find',str(Path.home()),'-maxdepth','6','-iname',f'*{q}*','-not','-path','*/.*']
                    out=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
                    results=out.stdout.strip().split('\n')[:50]
                except: pass
                for d in self.drives:
                    if d["mount"] and os.path.exists(d["mount"]):
                        try:
                            cmd=['find',d["mount"],'-maxdepth','4','-iname',f'*{q}*','-not','-path','*/.*']
                            out=subprocess.run(cmd,capture_output=True,text=True,timeout=8)
                            results.extend(out.stdout.strip().split('\n')[:20])
                        except: pass
            results=[r for r in results if r and os.path.exists(r)]
            GLib.idle_add(self._ss_show, results)
        threading.Thread(target=go,daemon=True).start()

    def _ss_show(self, results):
        self._clr(self.ss_res); self.sbar.set_text(f"{len(results)} results")
        smooth = self.S.get("perf_mode","normal") == "smooth"
        for idx, ps in enumerate(results[:50]):
            p=Path(ps); row=Gtk.Box(spacing=10); row.add_css_class("ss-result")
            if smooth: row.set_opacity(0)
            ic=Gtk.Image.new_from_icon_name(self._sys_icon(p)); ic.set_pixel_size(16)
            ic.add_css_class("folder-icon" if p.is_dir() else "file-icon"); row.append(ic)
            vb=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=1)
            nl=Gtk.Label(label=p.name); nl.set_xalign(0); nl.add_css_class("file-name"); vb.append(nl)
            pl=Gtk.Label(label=str(p.parent)); pl.set_xalign(0); pl.add_css_class("sidebar-meta")
            pl.set_ellipsize(Pango.EllipsizeMode.MIDDLE); vb.append(pl)
            row.append(vb)
            ck=Gtk.GestureClick()
            ck.connect("pressed",lambda g,n,x,y,pp=p: (self.nav_to(pp.parent if pp.is_file() else pp), self.ss_rev.set_reveal_child(False)))
            row.add_controller(ck); self.ss_res.append(row)
            if smooth: GLib.timeout_add(15 * idx, self._fade_in, row)

    # =========================================================
    #                 SETTINGS PANEL
    # =========================================================
    def _build_settings(self):
        self._pending_changes = False
        self._original_settings = {k: v for k, v in self.S.items()}
        self._settings_rows = []  # For search filtering
        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # Search bar at top
        search_box = Gtk.Box(spacing=6)
        search_box.set_margin_start(12); search_box.set_margin_end(12); search_box.set_margin_top(8)
        self._settings_search = Gtk.SearchEntry()
        self._settings_search.set_placeholder_text("Search settings...")
        self._settings_search.set_hexpand(True)
        self._settings_search.connect("search-changed", self._filter_settings)
        search_box.append(self._settings_search)
        wrapper.append(search_box)
        # Live preview area - mini file manager mockup
        self._preview_da = Gtk.DrawingArea()
        self._preview_da.set_size_request(-1, 140)
        self._preview_da.set_content_height(140)
        self._preview_da.set_margin_start(12); self._preview_da.set_margin_end(12)
        self._preview_da.set_margin_top(8); self._preview_da.set_margin_bottom(4)
        self._preview_da.set_draw_func(self._draw_preview)
        wrapper.append(self._preview_da)
        # Scrollable panel
        panel=Gtk.Box(orientation=Gtk.Orientation.VERTICAL); panel.add_css_class("settings-panel")
        self._settings_panel = panel
        sc=Gtk.ScrolledWindow(); sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        sc.set_child(panel); sc.set_vexpand(True); wrapper.append(sc)
        # Apply/Cancel bar (hidden initially)
        self._apply_bar = Gtk.Box(spacing=8)
        self._apply_bar.add_css_class("apply-bar")
        self._apply_bar.set_margin_start(12); self._apply_bar.set_margin_end(12)
        self._apply_bar.set_margin_top(6); self._apply_bar.set_margin_bottom(8)
        self._changes_lbl = Gtk.Label(label="No changes")
        self._changes_lbl.set_xalign(0); self._changes_lbl.set_hexpand(True)
        self._changes_lbl.add_css_class("settings-label"); self._changes_lbl.set_opacity(0.4)
        self._apply_bar.append(self._changes_lbl)
        self._cancel_btn = Gtk.Button(label="Cancel"); self._cancel_btn.add_css_class("flat")
        self._cancel_btn.set_sensitive(False)
        self._cancel_btn.connect("clicked", self._settings_cancel); self._apply_bar.append(self._cancel_btn)
        self._apply_btn = Gtk.Button(label="Apply"); self._apply_btn.add_css_class("suggested-action")
        self._apply_btn.set_sensitive(False)
        self._apply_btn.connect("clicked", self._settings_apply_confirm); self._apply_bar.append(self._apply_btn)
        wrapper.append(self._apply_bar)
        self.srev.set_child(wrapper)
        t=Gtk.Label(label="Settings"); t.set_xalign(0); t.add_css_class("settings-title"); panel.append(t)

        # THEME
        sec=Gtk.Label(label="THEME"); sec.set_xalign(0); sec.add_css_class("settings-section"); panel.append(sec)
        self._tbns={}
        # Theme description display
        self._theme_desc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._theme_desc_box.set_margin_top(2); self._theme_desc_box.set_margin_bottom(6)
        self._theme_desc_title = Gtk.Label(); self._theme_desc_title.set_xalign(0)
        self._theme_desc_title.set_markup("<b>" + THEMES.get(self.S.get("theme","nova"),THEMES["nova"])["name"] + "</b>")
        self._theme_desc_title.add_css_class("settings-label")
        self._theme_desc_box.append(self._theme_desc_title)
        self._theme_desc_label = Gtk.Label(); self._theme_desc_label.set_xalign(0)
        self._theme_desc_label.set_wrap(True); self._theme_desc_label.set_max_width_chars(28)
        self._theme_desc_label.add_css_class("sidebar-meta")
        self._theme_desc_label.set_opacity(0.6)
        # Load description from file
        cur_tid = self.S.get("theme", "nova")
        desc_path = os.path.join(THEME_DESC_DIR, f"{cur_tid}.txt")
        try:
            with open(desc_path) as f: desc_text = f.read().strip()
        except: desc_text = ""
        self._theme_desc_label.set_text(desc_text)
        self._theme_desc_box.append(self._theme_desc_label)
        for chunk_start in range(0, len(THEMES), 3):
            row=Gtk.Box(spacing=4); row.set_margin_bottom(4)
            for tid,th in list(THEMES.items())[chunk_start:chunk_start+3]:
                b=Gtk.Button(label=th["name"]); b.add_css_class("theme-btn"); b.add_css_class("flat")
                if self.S.get("theme")==tid: b.add_css_class("active")
                b.connect("clicked",lambda b,t=tid: self._stheme(t)); self._tbns[tid]=b
                # Hover to show description
                hover = Gtk.EventControllerMotion()
                def on_hover_enter(ctrl, x, y, t=tid, th=th):
                    self._theme_desc_title.set_markup(f"<b>{th['name']}</b>")
                    dp = os.path.join(THEME_DESC_DIR, f"{t}.txt")
                    try:
                        with open(dp) as f: self._theme_desc_label.set_text(f.read().strip())
                    except: self._theme_desc_label.set_text("")
                hover.connect("enter", on_hover_enter)
                b.add_controller(hover)
                row.append(b)
            panel.append(row)
        panel.append(self._theme_desc_box)

        # Light / Blur / Dark 3-position toggle
        mode_row = Gtk.Box(spacing=8); mode_row.set_margin_top(6); mode_row.set_margin_bottom(8)
        mode_row.set_valign(Gtk.Align.CENTER)
        lbl_l = Gtk.Label(label="Light"); lbl_l.add_css_class("settings-label"); mode_row.append(lbl_l)
        self._mode_da = Gtk.DrawingArea(); self._mode_da.set_size_request(72, 26)
        self._mode_da.set_content_width(72); self._mode_da.set_content_height(26)
        cur_mode = self.S.get("display_mode", "dark")
        if cur_mode not in ("dark","blur","light"):
            cur_mode = "light" if self.S.get("light_mode", False) else "dark"
            self.S["display_mode"] = cur_mode; self._mark_changed()
        self._mode_positions = {"light": 0, "blur": 1, "dark": 2}
        self._mode_pos = self._mode_positions.get(cur_mode, 2)
        def draw_mode_toggle(da, cr, w, h, data=None):
            # Track background
            cr.set_source_rgba(1,1,1,0.08); radius = h/2
            cr.arc(radius, h/2, radius, math.pi/2, 3*math.pi/2)
            cr.arc(w-radius, h/2, radius, -math.pi/2, math.pi/2)
            cr.close_path(); cr.fill()
            # Thumb
            seg_w = w / 3; thumb_r = (h-6) / 2
            thumb_x = seg_w * self._mode_pos + seg_w / 2
            ar,ag,ab = self.S["accent_r"],self.S["accent_g"],self.S["accent_b"]
            cr.set_source_rgba(ar/255, ag/255, ab/255, 0.9)
            cr.arc(thumb_x, h/2, thumb_r, 0, math.pi*2); cr.fill()
            # Tick marks
            for i in range(3):
                tx = seg_w * i + seg_w / 2
                if i != self._mode_pos:
                    cr.set_source_rgba(1,1,1,0.2)
                    cr.arc(tx, h/2, 2, 0, math.pi*2); cr.fill()
        self._mode_da.set_draw_func(draw_mode_toggle)
        ck = Gtk.GestureClick()
        def on_mode_click(g, n, x, y):
            w = self._mode_da.get_width()
            seg = w / 3
            pos = min(2, max(0, int(x / seg)))
            modes = ["light", "blur", "dark"]
            mid = modes[pos]
            self._mode_pos = pos
            self.S["display_mode"] = mid
            self.S["light_mode"] = (mid == "light")
            self._mode_da.queue_draw()
            self._mark_changed()

        ck.connect("pressed", on_mode_click)
        self._mode_da.add_controller(ck)
        mode_row.append(self._mode_da)
        lbl_d = Gtk.Label(label="Dark"); lbl_d.add_css_class("settings-label"); mode_row.append(lbl_d)
        panel.append(mode_row)

        # ACCENT
        sec2=Gtk.Label(label="ACCENT COLOR"); sec2.set_xalign(0); sec2.add_css_class("settings-section"); panel.append(sec2)
        colors=[("Purple",136,130,255),("Blue",66,133,244),("Teal",0,188,180),("Green",52,199,89),("Orange",255,149,0),("Red",255,69,58),
            ("Pink",255,105,180),("Cyan",0,200,255),("Lavender",180,160,255),("Mint",102,212,170),("Yellow",255,204,0),("Coral",255,127,80)]
        for chunk in [colors[:6],colors[6:]]:
            crow=Gtk.Box(spacing=8); crow.set_margin_bottom(6)
            for name,r,g,b in chunk:
                da=Gtk.DrawingArea(); da.set_size_request(28,28); da.set_content_width(28); da.set_content_height(28)
                da.set_draw_func(lambda d,cr,w,h,c: (cr.arc(w/2,h/2,min(w,h)/2-1,0,PI2),cr.set_source_rgb(c[0]/255,c[1]/255,c[2]/255),cr.fill()), (r,g,b))
                self._tt(da,name)
                ck=Gtk.GestureClick(); ck.connect("pressed",lambda g,n,x,y,r_=r,g_=g,b_=b: self._sac(r_,g_,b_))
                da.add_controller(ck); crow.append(da)
            panel.append(crow)
        # Preview
        pr=Gtk.Box(); pr.set_halign(Gtk.Align.CENTER); pr.set_margin_top(4); pr.set_margin_bottom(6)
        self.acprev=Gtk.DrawingArea(); self.acprev.set_size_request(42,42); self.acprev.set_content_width(42); self.acprev.set_content_height(42)
        self.acprev.set_draw_func(lambda d,cr,w,h: (cr.arc(w/2,h/2,min(w,h)/2-1,0,PI2),cr.set_source_rgb(self.S["accent_r"]/255,self.S["accent_g"]/255,self.S["accent_b"]/255),cr.fill()))
        pr.append(self.acprev); panel.append(pr)

        # CUSTOM COLOR
        sec_c=Gtk.Label(label="CUSTOM COLOR"); sec_c.set_xalign(0); sec_c.add_css_class("settings-section"); panel.append(sec_c)
        for label,attr,lo,hi in [("Hue","hue",0,360),("Saturation","sat",0,100),("Brightness","bri",0,100)]:
            r=Gtk.Box(spacing=6); r.add_css_class("settings-row")
            l=Gtk.Label(label=label); l.set_xalign(0); l.set_hexpand(True); l.add_css_class("settings-label"); r.append(l)
            e=Gtk.Entry(); e.set_width_chars(4); e.add_css_class("settings-entry"); r.append(e)
            setattr(self,f'{attr}_e',e); panel.append(r)
            sl=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,lo,hi,1)
            sl.set_draw_value(False); sl.set_margin_bottom(4); sl.connect("value-changed",self._hsb_chg)
            setattr(self,f'{attr}_sl',sl); panel.append(sl)
        hr=Gtk.Box(spacing=6); hr.set_margin_top(4); hr.add_css_class("settings-row")
        self.hexe=Gtk.Entry(); self.hexe.set_width_chars(10); self.hexe.set_hexpand(True)
        self.hexe.add_css_class("settings-entry"); self.hexe.connect("activate",self._hex_apply); hr.append(self.hexe)
        ab=Gtk.Button(label="Apply"); ab.add_css_class("apply-btn"); ab.add_css_class("flat")
        ab.connect("clicked",lambda b: self._hex_apply(self.hexe)); hr.append(ab)
        panel.append(hr); self._sync_hsb()

        # ICON STYLE
        sec_i=Gtk.Label(label="ICON STYLE"); sec_i.set_xalign(0); sec_i.add_css_class("settings-section"); panel.append(sec_i)
        irow=Gtk.Box(spacing=4); self._ibns={}
        for tid,name in ICON_STYLES.items():
            if tid == "pack" and not self.icon_packs: continue
            b=Gtk.Button(label=name); b.add_css_class("theme-btn"); b.add_css_class("flat")
            if self.S.get("icon_style","system")==tid: b.add_css_class("active")
            b.connect("clicked",lambda b,t=tid: self._sicon(t)); self._ibns[tid]=b; irow.append(b)
        panel.append(irow)
        # Icon pack selector (if packs exist)
        if self.icon_packs:
            ip_row=Gtk.Box(spacing=4); ip_row.set_margin_top(4)
            for pname in self.icon_packs:
                b=Gtk.Button(label=pname); b.add_css_class("theme-btn"); b.add_css_class("flat")
                if self.S.get("icon_pack")==pname and self.S.get("icon_style")=="pack": b.add_css_class("active")
                def pick_pack(b, n=pname):
                    self.S["icon_style"]="pack"; self.S["icon_pack"]=n; self._mark_changed()
                    for k,bb in self._ibns.items(): bb.remove_css_class("active")
                    if "pack" in self._ibns: self._ibns["pack"].add_css_class("active")
                    self._mark_changed()
                b.connect("clicked",pick_pack); ip_row.append(b)
            panel.append(ip_row)
        # Open icon packs folder button
        ipb = Gtk.Button(label="Open Icon Packs Folder"); ipb.add_css_class("flat"); ipb.add_css_class("theme-btn")
        ipb.set_halign(Gtk.Align.START); ipb.set_margin_top(4)
        ipb.connect("clicked", lambda b: subprocess.Popen(['xdg-open', ICON_PACKS_DIR])); panel.append(ipb)

        # FONT
        sec_f=Gtk.Label(label="FONT"); sec_f.set_xalign(0); sec_f.add_css_class("settings-section"); panel.append(sec_f)
        self.font_btn = Gtk.Button(label=self.S.get("font_family","system-ui"))
        self.font_btn.add_css_class("theme-btn"); self.font_btn.add_css_class("flat")
        self.font_btn.connect("clicked", self._show_font_picker); panel.append(self.font_btn)
        sr=Gtk.Box(spacing=8); sr.add_css_class("settings-row"); sr.set_margin_top(4)
        sl=Gtk.Label(label="Size"); sl.set_xalign(0); sl.add_css_class("settings-label"); sr.append(sl)
        self.fsz_e=Gtk.Entry(); self.fsz_e.set_text(str(self.S.get("font_size",13)))
        self.fsz_e.set_width_chars(4); self.fsz_e.add_css_class("settings-entry")
        self.fsz_e.connect("activate",lambda e: self._upd("font_size",max(8,min(24,int(e.get_text()))))); sr.append(self.fsz_e)
        panel.append(sr)

        # LAYOUT
        sec3=Gtk.Label(label="LAYOUT"); sec3.set_xalign(0); sec3.add_css_class("settings-section"); panel.append(sec3)
        for label,key,lo,hi in [("UI Scale","ui_scale",0.8,2.0),("Icon (List)","icon_size_list",14,32),
            ("Icon (Grid)","icon_size_grid",32,80),("Row Height","row_height",28,52)]:
            r=Gtk.Box(spacing=8); r.add_css_class("settings-row")
            l=Gtk.Label(label=label); l.set_xalign(0); l.set_hexpand(True); l.add_css_class("settings-label"); r.append(l)
            e=Gtk.Entry(); e.set_text(str(self.S[key])); e.set_width_chars(5); e.add_css_class("settings-entry")
            e.connect("activate",lambda ent,k=key,lo_=lo,hi_=hi: self._layout_e(ent,k,lo_,hi_)); r.append(e); panel.append(r)

        # CUSTOMIZE
        sec4=Gtk.Label(label="CUSTOMIZE"); sec4.set_xalign(0); sec4.add_css_class("settings-section"); panel.append(sec4)
        for label,path in [("Edit custom.css",CUSTOM_CSS),("Config folder",CFG_DIR)]:
            b=Gtk.Button(label=label); b.add_css_class("flat"); b.add_css_class("theme-btn"); b.set_halign(Gtk.Align.START)
            b.connect("clicked",lambda b,p=path: subprocess.Popen(['xdg-open',p])); panel.append(b)

        # PERFORMANCE MODE
        sec5=Gtk.Label(label="PERFORMANCE"); sec5.set_xalign(0); sec5.add_css_class("settings-section"); panel.append(sec5)
        perf_box = Gtk.Box(spacing=6); perf_box.set_margin_bottom(8)
        cur_perf = self.S.get("perf_mode", "normal")
        for mode, label, desc in [("smooth","Smooth","Animations everywhere"),("normal","Normal","Balanced"),("fast","Fast","Zero animations")]:
            pb = Gtk.Button(label=label); pb.add_css_class("flat"); pb.add_css_class("theme-btn")
            if cur_perf == mode: pb.add_css_class("active-tab")
            pb.set_tooltip_text(desc)
            pb.connect("clicked", lambda b, m=mode: self._set_perf(m))
            perf_box.append(pb)
        panel.append(perf_box)

        # GENERAL
        sec_g=Gtk.Label(label="GENERAL"); sec_g.set_xalign(0); sec_g.add_css_class("settings-section"); panel.append(sec_g)
        # Default view mode
        vr=Gtk.Box(spacing=8); vr.add_css_class("settings-row")
        vl=Gtk.Label(label="Default View"); vl.set_xalign(0); vl.set_hexpand(True); vl.add_css_class("settings-label"); vr.append(vl)
        vbox=Gtk.Box(spacing=4)
        for vid, vlbl in [("list","List"),("grid","Grid")]:
            vb=Gtk.Button(label=vlbl); vb.add_css_class("flat"); vb.add_css_class("theme-btn")
            if self.S.get("default_view","list")==vid: vb.add_css_class("active")
            def set_view(b, v=vid):
                self.S["default_view"]=v; self._mark_changed()
                for c in vbox: c.remove_css_class("active")
                b.add_css_class("active")
            vb.connect("clicked",set_view); vbox.append(vb)
        vr.append(vbox); panel.append(vr)
        # Show hidden files
        hr=Gtk.Box(spacing=8); hr.add_css_class("settings-row")
        hl=Gtk.Label(label="Show Hidden Files"); hl.set_xalign(0); hl.set_hexpand(True); hl.add_css_class("settings-label"); hr.append(hl)
        hs=Gtk.Switch(); hs.set_active(self.S.get("show_hidden",False))
        hs.set_valign(Gtk.Align.CENTER)
        def tog_hidden(sw, pspec):
            self.S["show_hidden"]=sw.get_active(); self._mark_changed()
        hs.connect("notify::active",tog_hidden); hr.append(hs); panel.append(hr)
        # Confirm before delete
        dr=Gtk.Box(spacing=8); dr.add_css_class("settings-row")
        dl=Gtk.Label(label="Confirm Delete"); dl.set_xalign(0); dl.set_hexpand(True); dl.add_css_class("settings-label"); dr.append(dl)
        ds=Gtk.Switch(); ds.set_active(self.S.get("confirm_delete",True))
        ds.set_valign(Gtk.Align.CENTER)
        ds.connect("notify::active", lambda sw,p: (self.S.__setitem__("confirm_delete",sw.get_active()), self._mark_changed()))
        dr.append(ds); panel.append(dr)
        # Single click to open
        scr=Gtk.Box(spacing=8); scr.add_css_class("settings-row")
        scl=Gtk.Label(label="Single Click Open"); scl.set_xalign(0); scl.set_hexpand(True); scl.add_css_class("settings-label"); scr.append(scl)
        scs=Gtk.Switch(); scs.set_active(self.S.get("single_click",False))
        scs.set_valign(Gtk.Align.CENTER)
        scs.connect("notify::active", lambda sw,p: (self.S.__setitem__("single_click",sw.get_active()), self._mark_changed()))
        scr.append(scs); panel.append(scr)
        # Thumbnail size for Quick Look
        qlr=Gtk.Box(spacing=8); qlr.add_css_class("settings-row")
        qll=Gtk.Label(label="Quick Look Size"); qll.set_xalign(0); qll.set_hexpand(True); qll.add_css_class("settings-label"); qlr.append(qll)
        qlbox=Gtk.Box(spacing=4)
        for sz, slbl in [("small","S"),("medium","M"),("large","L")]:
            qb=Gtk.Button(label=slbl); qb.add_css_class("flat"); qb.add_css_class("theme-btn")
            if self.S.get("ql_size","medium")==sz: qb.add_css_class("active")
            def set_ql(b, s=sz):
                self.S["ql_size"]=s; self._mark_changed()
                for c in qlbox: c.remove_css_class("active")
                b.add_css_class("active")
            qb.connect("clicked",set_ql); qlbox.append(qb)
        qlr.append(qlbox); panel.append(qlr)

        # BEHAVIOR
        sec_b=Gtk.Label(label="BEHAVIOR"); sec_b.set_xalign(0); sec_b.add_css_class("settings-section"); panel.append(sec_b)
        # Sort by
        sor=Gtk.Box(spacing=8); sor.add_css_class("settings-row")
        sol=Gtk.Label(label="Default Sort"); sol.set_xalign(0); sol.set_hexpand(True); sol.add_css_class("settings-label"); sor.append(sol)
        sobox=Gtk.Box(spacing=4)
        for sid, slbl in [("name","Name"),("date","Date"),("size","Size")]:
            sb=Gtk.Button(label=slbl); sb.add_css_class("flat"); sb.add_css_class("theme-btn")
            if self.S.get("default_sort","name")==sid: sb.add_css_class("active")
            def set_sort(b, s=sid):
                self.S["default_sort"]=s; self._mark_changed()
                for c in sobox: c.remove_css_class("active")
                b.add_css_class("active")
            sb.connect("clicked",set_sort); sobox.append(sb)
        sor.append(sobox); panel.append(sor)
        # Folders first
        ffr=Gtk.Box(spacing=8); ffr.add_css_class("settings-row")
        ffl=Gtk.Label(label="Folders First"); ffl.set_xalign(0); ffl.set_hexpand(True); ffl.add_css_class("settings-label"); ffr.append(ffl)
        ffs=Gtk.Switch(); ffs.set_active(self.S.get("folders_first",True))
        ffs.set_valign(Gtk.Align.CENTER)
        ffs.connect("notify::active", lambda sw,p: (self.S.__setitem__("folders_first",sw.get_active()), self._mark_changed()))
        ffr.append(ffs); panel.append(ffr)
        # Show file extensions
        exr=Gtk.Box(spacing=8); exr.add_css_class("settings-row")
        exl=Gtk.Label(label="Show Extensions"); exl.set_xalign(0); exl.set_hexpand(True); exl.add_css_class("settings-label"); exr.append(exl)
        exs=Gtk.Switch(); exs.set_active(self.S.get("show_extensions",True))
        exs.set_valign(Gtk.Align.CENTER)
        exs.connect("notify::active", lambda sw,p: (self.S.__setitem__("show_extensions",sw.get_active()), self._mark_changed()))
        exr.append(exs); panel.append(exr)

        # KEYBINDS
        sec_k=Gtk.Label(label="KEYBOARD SHORTCUTS"); sec_k.set_xalign(0); sec_k.add_css_class("settings-section"); panel.append(sec_k)
        default_binds = self._get_default_keybinds()
        user_binds = self.S.get("keybinds", {})
        for action, default_key in default_binds.items():
            kr=Gtk.Box(spacing=8); kr.add_css_class("settings-row")
            kl=Gtk.Label(label=action); kl.set_xalign(0); kl.set_hexpand(True); kl.add_css_class("settings-label"); kr.append(kl)
            current = user_binds.get(action, default_key)
            kb=Gtk.Button(label=current); kb.add_css_class("flat"); kb.add_css_class("keybind-btn")
            kb.set_size_request(100, -1)
            def start_rebind(b, act=action):
                b.set_label("Press key...")
                b.add_css_class("recording")
                self._rebind_action = act
                self._rebind_btn = b
            kb.connect("clicked", start_rebind)
            kr.append(kb); panel.append(kr)
        # Reset keybinds button
        rst=Gtk.Button(label="Reset to Defaults"); rst.add_css_class("flat"); rst.add_css_class("theme-btn")
        rst.set_halign(Gtk.Align.START); rst.set_margin_top(4)
        def reset_binds(b):
            self.S["keybinds"]={}; self._mark_changed()
            self._build_settings()
        rst.connect("clicked", reset_binds); panel.append(rst)

        # ABOUT
        sec_a=Gtk.Label(label="ABOUT"); sec_a.set_xalign(0); sec_a.add_css_class("settings-section"); panel.append(sec_a)
        ver=Gtk.Label(label="Nebula Files v4.2.0"); ver.set_xalign(0); ver.add_css_class("settings-label"); ver.set_opacity(0.6); panel.append(ver)
        abt=Gtk.Label(label="A modern file manager for Linux"); abt.set_xalign(0); abt.add_css_class("sidebar-meta"); abt.set_opacity(0.5); panel.append(abt)
        # Spacer
        sp=Gtk.Box(); sp.set_size_request(-1, 20); panel.append(sp)

    def _stag(self, widget, keywords):
        """Tag a settings widget with searchable keywords"""
        self._settings_rows.append((widget, keywords.lower()))
        return widget

    def _draw_preview(self, da, cr, w, h, data=None):
        """Draw mini file manager preview with current pending settings"""
        import cairo
        sc = self.S.get("ui_scale", 1.3)
        is_dark = not self.S.get("light_mode", False)
        ar, ag, ab = self.S.get("accent_r",136)/255, self.S.get("accent_g",130)/255, self.S.get("accent_b",255)/255
        font = self.S.get("font_family", "system-ui")
        icon_style = self.S.get("icon_style", "system")

        # Background
        rad = 10
        if is_dark:
            bg_r, bg_g, bg_b = 0.14, 0.14, 0.16
            fg_r, fg_g, fg_b = 1.0, 1.0, 1.0
            sb_r, sb_g, sb_b = 0.11, 0.11, 0.13
            row_hover = (1, 1, 1, 0.04)
        else:
            bg_r, bg_g, bg_b = 0.97, 0.97, 0.98
            fg_r, fg_g, fg_b = 0.1, 0.1, 0.1
            sb_r, sb_g, sb_b = 0.93, 0.93, 0.94
            row_hover = (0, 0, 0, 0.03)

        # Rounded rect helper
        def rrect(x, y, rw, rh, r):
            cr.arc(x+r, y+r, r, math.pi, 3*math.pi/2)
            cr.arc(x+rw-r, y+r, r, 3*math.pi/2, 0)
            cr.arc(x+rw-r, y+rh-r, r, 0, math.pi/2)
            cr.arc(x+r, y+rh-r, r, math.pi/2, math.pi)
            cr.close_path()

        # Window background
        rrect(0, 0, w, h, rad)
        cr.set_source_rgb(bg_r, bg_g, bg_b); cr.fill()

        # Window border
        rrect(0, 0, w, h, rad)
        if is_dark: cr.set_source_rgba(1, 1, 1, 0.06)
        else: cr.set_source_rgba(0, 0, 0, 0.08)
        cr.set_line_width(1); cr.stroke()

        # Sidebar
        sb_w = int(w * 0.28)
        rrect(0, 0, sb_w, h, rad)
        cr.set_source_rgb(sb_r, sb_g, sb_b); cr.fill()
        # Clip right side of sidebar (no rounded corner on right)
        cr.rectangle(sb_w - rad, 0, rad, h)
        cr.set_source_rgb(sb_r, sb_g, sb_b); cr.fill()

        # Sidebar separator
        cr.set_source_rgba(fg_r, fg_g, fg_b, 0.06)
        cr.rectangle(sb_w, 0, 1, h); cr.fill()

        # Sidebar items
        cr.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9)
        sidebar_items = [("Home", True), ("Documents", False), ("Downloads", False), ("Music", False), ("Pictures", False)]
        for i, (name, active) in enumerate(sidebar_items):
            iy = 12 + i * 20
            if active:
                cr.set_source_rgba(ar, ag, ab, 0.15)
                rrect(4, iy - 2, sb_w - 8, 18, 4); cr.fill()
                cr.set_source_rgba(ar, ag, ab, 1.0)
            else:
                cr.set_source_rgba(fg_r, fg_g, fg_b, 0.5)
            # Folder icon (small square)
            cr.rectangle(12, iy + 2, 8, 7); cr.fill()
            cr.set_source_rgba(fg_r, fg_g, fg_b, 0.8 if active else 0.5)
            cr.move_to(26, iy + 11); cr.show_text(name)

        # Titlebar / breadcrumb
        cr.set_source_rgba(fg_r, fg_g, fg_b, 0.5)
        cr.set_font_size(8)
        cr.move_to(sb_w + 12, 16); cr.show_text("Home")
        cr.set_source_rgba(fg_r, fg_g, fg_b, 0.25)
        cr.move_to(sb_w + 38, 16); cr.show_text("›")
        cr.set_source_rgba(fg_r, fg_g, fg_b, 0.8)
        cr.move_to(sb_w + 46, 16); cr.show_text("Documents")

        # Separator under breadcrumb
        cr.set_source_rgba(fg_r, fg_g, fg_b, 0.06)
        cr.rectangle(sb_w + 1, 24, w - sb_w - 1, 1); cr.fill()

        # File rows
        content_x = sb_w + 8
        content_w = w - sb_w - 16
        files = [("Projects", True, True), ("report.pdf", False, False), ("photo.jpg", False, False), ("notes.md", False, False), ("data.csv", False, False)]
        cr.set_font_size(10)
        for i, (name, is_dir, selected) in enumerate(files):
            ry = 30 + i * 20
            # Selected row highlight
            if selected:
                cr.set_source_rgba(ar, ag, ab, 0.12)
                rrect(content_x, ry, content_w, 18, 4); cr.fill()
            elif i == 2:  # Hover effect on one row
                cr.set_source_rgba(*row_hover)
                rrect(content_x, ry, content_w, 18, 4); cr.fill()

            # Icon
            ix = content_x + 6; iy_c = ry + 4
            if is_dir:
                # Folder icon with accent tint
                cr.set_source_rgba(ar, ag, ab, 0.7)
                cr.rectangle(ix, iy_c, 12, 9); cr.fill()
                cr.rectangle(ix, iy_c - 2, 6, 3); cr.fill()
            else:
                # File icon
                cr.set_source_rgba(fg_r, fg_g, fg_b, 0.2)
                cr.rectangle(ix + 1, iy_c - 1, 10, 12); cr.fill()
                cr.set_source_rgba(fg_r, fg_g, fg_b, 0.1)
                cr.rectangle(ix + 3, iy_c + 2, 6, 1); cr.fill()
                cr.rectangle(ix + 3, iy_c + 5, 6, 1); cr.fill()

            # Filename
            cr.set_source_rgba(fg_r, fg_g, fg_b, 0.85)
            cr.move_to(ix + 18, ry + 13); cr.show_text(name)

            # Date (right side)
            cr.set_source_rgba(fg_r, fg_g, fg_b, 0.3)
            cr.set_font_size(8)
            cr.move_to(content_x + content_w - 60, ry + 12); cr.show_text("05 Mar 2026")
            cr.set_font_size(10)

        # Status bar
        cr.set_source_rgba(fg_r, fg_g, fg_b, 0.04)
        cr.rectangle(sb_w + 1, h - 18, w - sb_w - 1, 18); cr.fill()
        cr.set_source_rgba(fg_r, fg_g, fg_b, 0.35)
        cr.set_font_size(8)
        cr.move_to(sb_w + 10, h - 6); cr.show_text("1 folder, 4 files")

    def _refresh_preview(self):
        """Refresh the mini preview when settings change"""
        if hasattr(self, '_preview_da'):
            self._preview_da.queue_draw()

    def _filter_settings(self, entry):
        """Filter settings by searching label text in all children"""
        query = entry.get_text().strip().lower()
        panel = self._settings_panel
        current_section = None
        section_widgets = []
        section_match = False
        # Group widgets by section
        for child in list(panel):
            if hasattr(child, 'get_css_classes') and 'settings-section' in child.get_css_classes():
                # Apply visibility to previous section
                if current_section is not None:
                    current_section.set_visible(not query or section_match)
                    for w in section_widgets:
                        w.set_visible(not query or section_match)
                current_section = child
                section_widgets = []
                section_match = not query or query in child.get_label().lower()
            elif current_section is not None:
                section_widgets.append(child)
                # Check if any label in this row matches
                if not section_match:
                    text = self._get_widget_text(child).lower()
                    if query in text:
                        section_match = True
            elif hasattr(child, 'get_css_classes') and 'settings-title' in child.get_css_classes():
                child.set_visible(not query)
        # Handle last section
        if current_section is not None:
            current_section.set_visible(not query or section_match)
            for w in section_widgets:
                w.set_visible(not query or section_match)

    def _get_widget_text(self, widget):
        """Recursively get all text from a widget tree"""
        texts = []
        if hasattr(widget, 'get_label') and widget.get_label():
            texts.append(widget.get_label())
        if hasattr(widget, 'get_text') and callable(widget.get_text):
            try: texts.append(widget.get_text())
            except: pass
        if hasattr(widget, 'get_tooltip_text') and widget.get_tooltip_text():
            texts.append(widget.get_tooltip_text())
        # Recurse into children
        child = widget.get_first_child() if hasattr(widget, 'get_first_child') else None
        while child:
            texts.append(self._get_widget_text(child))
            child = child.get_next_sibling()
        return " ".join(texts)

    def _mark_changed(self):
        """Show apply bar when settings change, refresh preview"""
        self._pending_changes = True
        self._refresh_preview()
        if hasattr(self, '_apply_bar'):
            count = sum(1 for k, v in self.S.items() if k in self._original_settings and self._original_settings[k] != v)
            if count > 0:
                self._apply_btn.set_sensitive(True)
                self._cancel_btn.set_sensitive(True)
                self._changes_lbl.set_label(f"{count} unsaved change{'s' if count != 1 else ''}")
                self._changes_lbl.set_opacity(0.7)

    def _settings_cancel(self, btn=None):
        """Revert all changes to original"""
        self.S.clear()
        self.S.update(self._original_settings)
        save_cfg(self.S)
        self._pending_changes = False
        self.vmode = self.S.get("default_view", "list")
        self.T.hidden = self.S.get("show_hidden", False)
        # Rebuild main app with reverted settings
        self._apply_css()
        self._rebuild_bars()
        self._load()
        # Reset apply bar buttons
        if hasattr(self, '_apply_btn'):
            self._apply_btn.set_sensitive(False)
            self._cancel_btn.set_sensitive(False)
            self._changes_lbl.set_label("No changes"); self._changes_lbl.set_opacity(0.4)
        # Update theme buttons to match reverted theme
        cur_theme = self.S.get("theme", "nova")
        if hasattr(self, '_tbns'):
            for k, b in self._tbns.items():
                if k == cur_theme: b.add_css_class("active")
                else: b.remove_css_class("active")
        # Update icon style buttons
        cur_icon = self.S.get("icon_style", "system")
        if hasattr(self, '_ibns'):
            for k, b in self._ibns.items():
                if k == cur_icon: b.add_css_class("active")
                else: b.remove_css_class("active")
        # Sync accent color sliders
        if hasattr(self, 'hue_sl'): self._sync_hsb()
        if hasattr(self, 'acprev'): self.acprev.queue_draw()
        # Update display mode toggle
        if hasattr(self, '_mode_da'):
            dm = self.S.get("display_mode", "blur")
            self._mode_pos = ["light", "blur", "dark"].index(dm) if dm in ["light", "blur", "dark"] else 1
            self._mode_da.queue_draw()
        # Refresh preview
        self._refresh_preview()
        self.sbar.set_text("Settings reverted")

    def _settings_apply_confirm(self, btn=None):
        """Show confirmation dialog before saving"""
        d = Adw.MessageDialog(transient_for=self)
        d.set_heading("Apply Changes?")
        d.set_body("Save your settings changes? This will update your configuration.")
        d.add_response("cancel", "Cancel")
        d.add_response("apply", "Apply")
        d.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
        def on_resp(dlg, resp):
            dlg.close()
            if resp == "apply":
                save_cfg(self.S)
                self._original_settings = {k: v for k, v in self.S.items()}
                self._pending_changes = False
                self._apply_btn.set_sensitive(False)
                self._cancel_btn.set_sensitive(False)
                self._changes_lbl.set_label("No changes"); self._changes_lbl.set_opacity(0.4)
                # Check if theme changed to Win11 (needs restart)
                if self.S.get("theme") == "windows":
                    rd = Adw.MessageDialog(transient_for=self)
                    rd.set_heading("Restart Required")
                    rd.set_body("Windows 11 theme uses a separate optimized app.\nRestart Nebula Files to apply.")
                    rd.add_response("later", "Later")
                    rd.add_response("restart", "Restart Now")
                    rd.set_response_appearance("restart", Adw.ResponseAppearance.SUGGESTED)
                    def on_restart(d2, r2):
                        d2.close()
                        if r2 == "restart":
                            import sys
                            launcher = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova-files-launcher.py")
                            if not os.path.exists(launcher):
                                launcher = os.path.expanduser("~/.local/share/nebula-files/nova-files-launcher.py")
                            if os.path.exists(launcher):
                                subprocess.Popen(["bash", "-c", f"sleep 0.5 && python3 {launcher}"])
                            self.get_application().quit()
                    rd.connect("response", on_restart); rd.present()
                    return
                # Apply changes to main app
                self.vmode = self.S.get("default_view", "list")
                self.T.hidden = self.S.get("show_hidden", False)
                self._apply_css(); self._rebuild_bars(); self._load()
                if hasattr(self,'hue_sl'): self._sync_hsb()
                if hasattr(self,'acprev'): self.acprev.queue_draw()
                toast = Adw.Toast(title="Settings saved")
                toast.set_timeout(2)
                self._toast_overlay.add_toast(toast)
        d.connect("response", on_resp); d.present()

    def _show_font_picker(self, btn):
        pop = Gtk.Popover(); pop.set_parent(btn); pop.set_has_arrow(False)
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        main_box.set_margin_top(8); main_box.set_margin_bottom(8)
        main_box.set_margin_start(8); main_box.set_margin_end(8)
        font_entry = Gtk.Entry()
        font_entry.set_placeholder_text("Type font name or Google Font...")
        font_entry.set_text(self.S.get("font_family", "system-ui"))
        main_box.append(font_entry)
        apply_row = Gtk.Box(spacing=6)
        apply_btn = Gtk.Button(label="Apply Custom Font")
        apply_btn.add_css_class("flat"); apply_btn.add_css_class("theme-btn")
        def apply_custom(b):
            font = font_entry.get_text().strip()
            if font:
                self.S["font_family"] = font; self._mark_changed()
                self.font_btn.set_label(font)
                pop.popdown(); self._mark_changed()
        apply_btn.connect("clicked", apply_custom)
        font_entry.connect("activate", lambda e: apply_custom(None))
        apply_row.append(apply_btn); main_box.append(apply_row)
        sep = Gtk.Separator(); sep.set_margin_top(4); sep.set_margin_bottom(4)
        main_box.append(sep)
        sc = Gtk.ScrolledWindow(); sc.set_min_content_height(250); sc.set_max_content_height(350)
        sc.set_min_content_width(220); sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.add_css_class("font-list")
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        cur = self.S.get("font_family","system-ui")
        google_fonts = ["Inter", "Roboto", "Open Sans", "Montserrat", "Lato", "Poppins",
            "Source Sans 3", "Nunito", "Raleway", "Ubuntu", "Fira Sans", "JetBrains Mono",
            "Space Grotesk", "DM Sans", "Outfit", "Plus Jakarta Sans"]
        all_fonts = google_fonts + [f for f in self.fonts if f not in google_fonts]
        for f in all_fonts:
            fb = Gtk.Button(label=f); fb.add_css_class("flat"); fb.add_css_class("font-item")
            if f == cur: fb.add_css_class("active")
            def pick(b, font=f):
                self.S["font_family"] = font; self._mark_changed()
                self.font_btn.set_label(font)
                pop.popdown(); self._mark_changed()
            fb.connect("clicked", pick); vb.append(fb)
        sc.set_child(vb); main_box.append(sc)
        pop.set_child(main_box); pop.popup()

    # Settings helpers
    def _stheme(self, tid):
        self.S["theme"]=tid; 
        th = THEMES.get(tid, THEMES["nova"])
        if "accent" in th:
            r,g,b = th["accent"]
            self.S["accent_r"]=r; self.S["accent_g"]=g; self.S["accent_b"]=b
        if tid == "windows":
            self.S["light_mode"] = True
        for k,b in self._tbns.items():
            if k==tid: b.add_css_class("active")
            else: b.remove_css_class("active")
        if hasattr(self,'hue_sl'): self._sync_hsb()
        if hasattr(self,'acprev'): self.acprev.queue_draw()
        self._mark_changed()

    def _rebuild_bars(self):
        """Rebuild topbar + toolbar when theme changes"""
        if hasattr(self, '_topbar_w') and self._topbar_w.get_parent(): self.mbox.remove(self._topbar_w)
        if hasattr(self, '_toolbar_w') and self._toolbar_w.get_parent(): self.mbox.remove(self._toolbar_w)
        if self._is_win():
            self._build_win11_chrome()
        else:
            self._build_topbar(); self._build_toolbar()
        # Reorder so bars come before colhdr
        if hasattr(self, '_topbar_w') and self._topbar_w.get_parent():
            self.mbox.reorder_child_after(self._topbar_w, None)
        if hasattr(self, '_toolbar_w') and self._toolbar_w.get_parent():
            if hasattr(self, '_topbar_w') and self._topbar_w.get_parent():
                self.mbox.reorder_child_after(self._toolbar_w, self._topbar_w)
            else:
                self.mbox.reorder_child_after(self._toolbar_w, None)
        self.mbox.reorder_child_after(self.colhdr, self._toolbar_w)
        self._upd_bc()

    def _sicon(self, tid):
        self.S["icon_style"]=tid; self._mark_changed()
        for k,b in self._ibns.items():
            if k==tid: b.add_css_class("active")
            else: b.remove_css_class("active")

    def _sync_hsb(self):
        r,g,b=self.S["accent_r"]/255,self.S["accent_g"]/255,self.S["accent_b"]/255
        h,s,v=colorsys.rgb_to_hsv(r,g,b)
        self.hue_sl.set_value(h*360); self.sat_sl.set_value(s*100); self.bri_sl.set_value(v*100)
        self.hue_e.set_text(str(int(h*360))); self.sat_e.set_text(str(int(s*100))); self.bri_e.set_text(str(int(v*100)))
        self.hexe.set_text(f"#{self.S['accent_r']:02X}{self.S['accent_g']:02X}{self.S['accent_b']:02X}")

    def _hsb_chg(self, sl):
        h=self.hue_sl.get_value()/360; s=self.sat_sl.get_value()/100; v=self.bri_sl.get_value()/100
        self.hue_e.set_text(str(int(h*360))); self.sat_e.set_text(str(int(s*100))); self.bri_e.set_text(str(int(v*100)))
        r,g,b=colorsys.hsv_to_rgb(h,s,v); ri,gi,bi=int(r*255),int(g*255),int(b*255)
        self.hexe.set_text(f"#{ri:02X}{gi:02X}{bi:02X}")
        self.S["accent_r"]=ri; self.S["accent_g"]=gi; self.S["accent_b"]=bi
        self._mark_changed(); self.acprev.queue_draw()

    def _hex_apply(self, e):
        t=e.get_text().strip()
        if not t.startswith('#'): t='#'+t
        if len(t)==7:
            try: r,g,b=int(t[1:3],16),int(t[3:5],16),int(t[5:7],16); self._sac(r,g,b)
            except: pass

    def _sac(self, r, g, b):
        self.S["accent_r"]=r; self.S["accent_g"]=g; self.S["accent_b"]=b
        self._mark_changed()
        if hasattr(self,'hue_sl'): self._sync_hsb()
        if hasattr(self,'acprev'): self.acprev.queue_draw()

    def _upd(self, k, v): self.S[k]=v; self._mark_changed()

    def _layout_e(self, e, k, lo, hi):
        try:
            v=float(e.get_text().strip()); v=max(lo,min(hi,v))
            if k!="ui_scale": v=int(v)
            else: v=round(v,1)
            e.set_text(str(v)); self._upd(k,v)
        except: e.set_text(str(self.S[k]))

    def _get_default_keybinds(self):
        return {
            "Back": "Alt+Left",
            "Forward": "Alt+Right",
            "Search": "Ctrl+F",
            "Super Search": "Ctrl+Shift+F",
            "New Folder": "Ctrl+N",
            "Copy": "Ctrl+C",
            "Cut": "Ctrl+X",
            "Paste": "Ctrl+V",
            "Select All": "Ctrl+A",
            "Rename": "F2",
            "Delete": "Delete",
            "Undo": "Ctrl+Z",
            "Redo": "Ctrl+Y",
            "Properties": "Ctrl+I",
            "Quick Look": "Space",
            "New Tab": "Ctrl+T",
            "Close Tab": "Ctrl+W",
            "Toggle Hidden": "Ctrl+H",
            "Compress": "Ctrl+Shift+Z",
            "Refresh": "F5",
            "Split View": "Ctrl+\\",
        }

    def _handle_rebind(self, kv, state):
        """Handle key capture for rebinding"""
        if not getattr(self, '_rebind_action', None): return False
        parts = []
        if state & Gdk.ModifierType.CONTROL_MASK: parts.append("Ctrl")
        if state & Gdk.ModifierType.SHIFT_MASK: parts.append("Shift")
        if state & Gdk.ModifierType.ALT_MASK: parts.append("Alt")
        key_name = Gdk.keyval_name(kv)
        if key_name in ("Control_L","Control_R","Shift_L","Shift_R","Alt_L","Alt_R","Meta_L","Meta_R"):
            return True  # Wait for actual key
        if kv == Gdk.KEY_Escape:
            # Cancel rebind
            default = self._get_default_keybinds().get(self._rebind_action, "")
            current = self.S.get("keybinds", {}).get(self._rebind_action, default)
            self._rebind_btn.set_label(current)
            self._rebind_btn.remove_css_class("recording")
            self._rebind_action = None; self._rebind_btn = None
            return True
        # Map special keys
        special = {Gdk.KEY_space: "Space", Gdk.KEY_Delete: "Delete", Gdk.KEY_BackSpace: "Backspace",
                    Gdk.KEY_Return: "Enter", Gdk.KEY_F1: "F1", Gdk.KEY_F2: "F2", Gdk.KEY_F3: "F3",
                    Gdk.KEY_F4: "F4", Gdk.KEY_F5: "F5", Gdk.KEY_F6: "F6", Gdk.KEY_F7: "F7",
                    Gdk.KEY_F8: "F8", Gdk.KEY_F9: "F9", Gdk.KEY_F10: "F10", Gdk.KEY_F11: "F11", Gdk.KEY_F12: "F12",
                    Gdk.KEY_Left: "Left", Gdk.KEY_Right: "Right", Gdk.KEY_Up: "Up", Gdk.KEY_Down: "Down",
                    Gdk.KEY_Tab: "Tab", Gdk.KEY_Home: "Home", Gdk.KEY_End: "End"}
        if kv in special: parts.append(special[kv])
        else: parts.append(key_name.upper() if len(key_name) == 1 else key_name.capitalize())
        combo = "+".join(parts)
        if "keybinds" not in self.S: self.S["keybinds"] = {}
        self.S["keybinds"][self._rebind_action] = combo
        self._mark_changed()
        self._rebind_btn.set_label(combo)
        self._rebind_btn.remove_css_class("recording")
        self._rebind_action = None; self._rebind_btn = None
        return True

    def _set_perf(self, mode):
        self.S["perf_mode"] = mode; self._mark_changed()
        # Update revealer transitions
        if mode == "fast":
            # Use SLIDE with 0 duration instead of NONE (NONE can break allocation)
            self.srev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
            self.srev.set_transition_duration(0)
            if hasattr(self, 'ss_rev'):
                self.ss_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
                self.ss_rev.set_transition_duration(0)
        elif mode == "smooth":
            self.srev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
            self.srev.set_transition_duration(350)
            if hasattr(self, 'ss_rev'):
                self.ss_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
                self.ss_rev.set_transition_duration(350)
        else:
            self.srev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
            self.srev.set_transition_duration(200)
            if hasattr(self, 'ss_rev'):
                self.ss_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
                self.ss_rev.set_transition_duration(200)
        self._apply_css(); self._rebuild_full_ui(); self._load()
        self.sbar.set_text(f"Performance: {mode.capitalize()}")

    # =========================================================
    #                 NAVIGATION + FILE RENDERING
    # =========================================================
    def nav_to(self, path, push=True):
        path=Path(path)
        if not path.exists(): return
        if not path.is_dir(): self._open(path); return
        # If split active and right side is focused, update right pane
        if self._split_active and getattr(self, '_split_focus_right', False) and hasattr(self, '_split_right_tab'):
            t = self.tabs[self._split_right_tab]
            t.path = path; t.sel.clear()
            self._load_split_right()
            self._update_split_bc()
            self._tref()
            return
        self.T.path=path; self.T.sel.clear(); self.T.sel_w={}
        if push:
            if self.T.hi<len(self.T.hist)-1: self.T.hist=self.T.hist[:self.T.hi+1]
            if not self.T.hist or self.T.hist[-1]!=path: self.T.hist.append(path); self.T.hi=len(self.T.hist)-1
        self._upd_nav(); self._upd_bc(); self._upd_sb(); self._tref(); self._load()

    def _is_cloud_path(self, path):
        """Check if path is on a cloud mount (slow I/O)"""
        s = str(path)
        cloud_dir = os.path.join(CFG_DIR, "cloud")
        if s.startswith(cloud_dir): return True
        # Also check GVFS mounts
        if "/gvfs/" in s: return True
        return False

    def _load(self):
        self._clr(self.fc)
        # Restore visibility for non-home views
        if hasattr(self, 'ss_rev'): self.ss_rev.set_visible(True)
        self.colhdr.set_size_request(-1, -1)
        self.fc.set_margin_top(2)
        # v2.8.2: Special Home view with Quick Access grid + Recents
        if str(self.T.path) == str(Path.home()):
            self._load_home_view(); return
        # Cloud paths: show spinner and load async
        if self._is_cloud_path(self.T.path):
            self._load_cloud_async(); return
        try: entries=list(self.T.path.iterdir())
        except PermissionError:
            l=Gtk.Label(label="Permission denied"); l.add_css_class("empty-state"); l.set_vexpand(True)
            self.fc.append(l); self.sbar.set_text("Permission denied"); return
        if not self.T.hidden: entries=[e for e in entries if not e.name.startswith(".")]
        filt = getattr(self, "_active_filter", None)
        if filt == "dirs": entries = [e for e in entries if e.is_dir()]
        elif filt == "hidden": entries = [e for e in entries if e.name.startswith(".")]
        elif isinstance(filt, set): entries = [e for e in entries if e.is_dir() or e.suffix.lower() in filt]
        entries=self._sort(entries)
        self.colhdr.set_visible(self.vmode=="list")
        if not entries:
            l=Gtk.Label(label="Empty folder"); l.add_css_class("empty-state"); l.set_vexpand(True)
            self.fc.append(l); self.sbar.set_text("0 items"); return
        if self.vmode=="list": self._rlist(entries)
        else: self._rgrid(entries)
        d=sum(1 for e in entries if e.is_dir()); f=len(entries)-d
        self.sbar.set_text(f"{d} folders, {f} files")

    def _load_cloud_async(self):
        """Load cloud directory in background with spinner"""
        self.colhdr.set_visible(False)
        # Show loading spinner
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_halign(Gtk.Align.CENTER); box.set_valign(Gtk.Align.CENTER); box.set_vexpand(True)
        spinner = Gtk.Spinner(); spinner.set_size_request(32, 32); spinner.start()
        box.append(spinner)
        lbl = Gtk.Label(label="Loading cloud files..."); lbl.add_css_class("dim-label")
        box.append(lbl)
        self.fc.append(box)
        self.sbar.set_text("Loading...")
        load_path = self.T.path
        load_hidden = self.T.hidden
        def scan():
            try:
                entries = list(load_path.iterdir())
                if not load_hidden: entries = [e for e in entries if not e.name.startswith('.')]
                GLib.idle_add(self._finish_cloud_load, entries, load_path)
            except PermissionError:
                GLib.idle_add(self._finish_cloud_load, None, load_path)
            except Exception:
                GLib.idle_add(self._finish_cloud_load, [], load_path)
        threading.Thread(target=scan, daemon=True).start()

    def _finish_cloud_load(self, entries, expected_path):
        """Render cloud directory entries after async load"""
        # Make sure we're still on the same path
        if self.T.path != expected_path: return
        self._clr(self.fc)
        if entries is None:
            l = Gtk.Label(label="Permission denied"); l.add_css_class("empty-state"); l.set_vexpand(True)
            self.fc.append(l); self.sbar.set_text("Permission denied"); return
        entries = self._sort(entries)
        self.colhdr.set_visible(self.vmode == "list")
        if not entries:
            l = Gtk.Label(label="Empty folder"); l.add_css_class("empty-state"); l.set_vexpand(True)
            self.fc.append(l); self.sbar.set_text("0 items"); return
        if self.vmode == "list": self._rlist(entries)
        else: self._rgrid(entries)
        d = sum(1 for e in entries if e.is_dir()); f = len(entries) - d
        self.sbar.set_text(f"{d} folders, {f} files")

    def _load_home_view(self):
        """Win11-style Home: Quick Access folders grid on top, Recent files below"""
        self.colhdr.set_visible(False)
        self.colhdr.set_size_request(-1, 0)
        if hasattr(self, 'ss_rev'): self.ss_rev.set_visible(False)
        self.fc.set_margin_top(0)
        sc = self.S.get("ui_scale", 1.3)
        home = str(Path.home())

        # === QUICK ACCESS FOLDERS (grid) ===
        qa_label = Gtk.Label(label="Quick Access"); qa_label.set_xalign(0)
        qa_label.set_margin_start(16); qa_label.set_margin_top(4); qa_label.set_margin_bottom(8)
        qa_label.add_css_class("sidebar-heading"); self.fc.append(qa_label)

        qa_grid = Gtk.FlowBox(); qa_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        qa_grid.set_max_children_per_line(8); qa_grid.set_min_children_per_line(3)
        qa_grid.set_column_spacing(12); qa_grid.set_row_spacing(12)
        qa_grid.set_margin_start(16); qa_grid.set_margin_end(16); qa_grid.set_margin_bottom(8)
        qa_grid.set_homogeneous(True)

        # Standard folders + user quick access
        folders = [("Home","user-home-symbolic",home),
            ("Documents","folder-documents-symbolic",os.path.join(home,"Documents")),
            ("Downloads","folder-download-symbolic",os.path.join(home,"Downloads")),
            ("Music","folder-music-symbolic",os.path.join(home,"Music")),
            ("Pictures","folder-pictures-symbolic",os.path.join(home,"Pictures")),
            ("Videos","folder-videos-symbolic",os.path.join(home,"Videos")),
            ("Games","folder-games-symbolic",os.path.join(home,"Games"))]
        for qa in self.quick_access:
            folders.append((qa.get("name",Path(qa["path"]).name), "folder-symbolic", qa["path"]))

        for name, icon, path in folders:
            if not os.path.isdir(path): continue
            card = Gtk.Button(); card.add_css_class("flat"); card.add_css_class("qa-card")
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            vb.set_margin_top(12); vb.set_margin_bottom(12); vb.set_margin_start(8); vb.set_margin_end(8)
            ic = Gtk.Image.new_from_icon_name(icon); ic.set_pixel_size(32); ic.add_css_class("sidebar-icon")
            nl = Gtk.Label(label=name); nl.set_ellipsize(Pango.EllipsizeMode.END); nl.set_max_width_chars(12)
            vb.append(ic); vb.append(nl); card.set_child(vb)
            card.connect("clicked", lambda b, p=path: self.nav_to(Path(p)))
            qa_grid.append(card)
        self.fc.append(qa_grid)

        # Show All Files button
        show_all = Gtk.Button(label="Show All Files ▸"); show_all.add_css_class("flat")
        show_all.set_halign(Gtk.Align.START); show_all.set_margin_start(16); show_all.set_margin_bottom(8); show_all.set_opacity(0.5)
        show_all.connect("clicked", lambda b: self._load_home_full())
        self.fc.append(show_all)

        # === SEPARATOR ===
        sep = Gtk.Separator(); sep.set_margin_start(16); sep.set_margin_end(16)
        sep.set_margin_top(4); sep.set_margin_bottom(4); self.fc.append(sep)

        # === RECENT FILES ===
        rec_label = Gtk.Label(label="Recent"); rec_label.set_xalign(0)
        rec_label.set_margin_start(16); rec_label.set_margin_top(8); rec_label.set_margin_bottom(8)
        rec_label.add_css_class("sidebar-heading"); self.fc.append(rec_label)

        recents = load_recents()
        if not recents:
            el = Gtk.Label(label="No recent files yet"); el.add_css_class("empty-state"); el.set_opacity(0.4)
            el.set_margin_start(16); self.fc.append(el)
        else:
            for rec in recents[:15]:
                rp = Path(rec["path"])
                if not rp.exists(): continue
                row = Gtk.Box(spacing=12); row.set_margin_start(16); row.set_margin_end(16)
                row.set_margin_top(2); row.set_margin_bottom(2)
                row.add_css_class("file-row")
                # Icon
                ic = self._make_icon(rp, self.S.get("icon_size_list", 22))
                row.append(ic)
                # Name + path
                vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1); vb.set_hexpand(True)
                nl = Gtk.Label(label=rp.name); nl.set_xalign(0); nl.set_ellipsize(Pango.EllipsizeMode.END)
                pl = Gtk.Label(label=str(rp.parent)); pl.set_xalign(0); pl.add_css_class("sidebar-meta")
                pl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                vb.append(nl); vb.append(pl); row.append(vb)
                # Time
                try:
                    rt = datetime.fromisoformat(rec.get("time",""))
                    tl = Gtk.Label(label=self._ft(rt.timestamp())); tl.add_css_class("sidebar-meta"); row.append(tl)
                except: pass
                # Click handler
                btn = Gtk.Button(); btn.add_css_class("flat"); btn.set_child(row)
                btn.connect("clicked", lambda b, p=rp: self._open(p))
                self.fc.append(btn)

        self.sbar.set_text("Home")

    def _load_home_full(self):
        """Show regular file listing for home directory"""
        self._clr(self.fc)
        try: entries=list(self.T.path.iterdir())
        except PermissionError:
            l=Gtk.Label(label="Permission denied"); l.add_css_class("empty-state"); l.set_vexpand(True)
            self.fc.append(l); return
        if not self.T.hidden: entries=[e for e in entries if not e.name.startswith('.')]
        entries=self._sort(entries)
        self.colhdr.set_visible(self.vmode=="list")
        if not entries:
            l=Gtk.Label(label="Empty folder"); l.add_css_class("empty-state"); l.set_vexpand(True)
            self.fc.append(l); return
        if self.vmode=="list": self._rlist(entries)
        else: self._rgrid(entries)
        d=sum(1 for e in entries if e.is_dir()); f=len(entries)-d
        self.sbar.set_text(f"{d} folders, {f} files")

    def _clr(self, c):
        ch=c.get_first_child()
        while ch: n=ch.get_next_sibling(); c.remove(ch); ch=n

    def _sort(self, entries):
        dirs=sorted([e for e in entries if e.is_dir()], key=lambda e: e.name.lower(), reverse=self.T.sort_rev if self.T.sort_by=="name" else False)
        files=sorted([e for e in entries if not e.is_dir()], key=lambda e: e.name.lower(), reverse=self.T.sort_rev if self.T.sort_by=="name" else False)
        if self.T.sort_by=="modified":
            dirs.sort(key=lambda e: self._mt(e), reverse=not self.T.sort_rev)
            files.sort(key=lambda e: self._mt(e), reverse=not self.T.sort_rev)
        elif self.T.sort_by=="size":
            files.sort(key=lambda e: self._sz(e), reverse=not self.T.sort_rev)
        return dirs+files

    def _sortby(self, k):
        if self.T.sort_by==k: self.T.sort_rev=not self.T.sort_rev
        else: self.T.sort_by=k; self.T.sort_rev=False
        self._load()

    def _make_icon(self, entry, size):
        """Create icon widget - system, custom drawn, or icon pack"""
        style = self._cur_icon_style()
        
        # Icon pack mode
        if style == "pack" and self.icon_packs and GdkPixbuf:
            pack_name = self.S.get("icon_pack","")
            pack = self.icon_packs.get(pack_name)
            if pack:
                ftype = get_file_type(entry)
                # Try specific type, then folder/file fallback, then generic
                icon_path = pack.get(ftype)
                if not icon_path and entry.is_dir(): icon_path = pack.get("folder")
                if not icon_path and entry.is_file(): icon_path = pack.get("file")
                if not icon_path: icon_path = pack.get("generic")
                if icon_path and os.path.exists(icon_path):
                    try:
                        # Use higher resolution and let GTK scale down for crisp display
                        render_size = max(size, 48)  # Render at least 48px for quality
                        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, render_size, render_size, True)
                        img = Gtk.Image.new_from_pixbuf(pb)
                        img.set_pixel_size(size)  # Display at requested size
                        return img
                    except: pass
            # Fallback to system
            style = "system"
        
        if style == "system":
            ic = Gtk.Image.new_from_icon_name(self._sys_icon(entry))
            ic.set_pixel_size(size)
            ic.add_css_class("folder-icon" if entry.is_dir() else "file-icon")
            return ic
        # Custom drawn icon
        ftype = get_file_type(entry)
        ar,ag,ab = self.S["accent_r"]/255, self.S["accent_g"]/255, self.S["accent_b"]/255
        th = self._cur_theme(); fgstr = th["fg"]
        fr,fg_,fb = [int(x)/255 for x in fgstr.split(",")]
        if entry.is_dir(): cr,cg,cb = ar,ag,ab
        else: cr,cg,cb = fr*0.6,fg_*0.6,fb*0.6

        da = Gtk.DrawingArea(); da.set_size_request(size,size)
        da.set_content_width(size); da.set_content_height(size)
        pad = max(2, size * 0.1)  # 10% padding so icons don't clip in grid
        # v2.0.7: Pass all values as user_data tuple — GTK4 sends it as 5th arg to callback
        draw_data = (pad, cr, cg, cb, ftype, style)
        da.set_draw_func(lambda d,c,w,h,data: draw_custom_icon(c, data[0], data[0], w-data[0]*2, data[1], data[2], data[3], data[4], data[5]), draw_data)
        return da

    def _rlist(self, entries):
        ils=int(self.S["icon_size_list"]*self.S["ui_scale"])
        smooth = self.S.get("perf_mode","normal") == "smooth"
        for idx, entry in enumerate(entries):
            row=Gtk.Box(spacing=12); row.add_css_class("file-row")
            if smooth: row.set_opacity(0)
            row.append(self._make_icon(entry, ils))
            nl=Gtk.Label(label=entry.name); nl.set_xalign(0); nl.set_hexpand(True)
            nl.set_ellipsize(Pango.EllipsizeMode.MIDDLE); nl.add_css_class("file-name"); row.append(nl)
            ml=Gtk.Label(label=self._ft(self._mt(entry))); ml.set_size_request(170,-1)
            ml.set_xalign(1); ml.add_css_class("file-meta"); row.append(ml)
            if entry.is_file(): ss=fmt_bytes(self._sz(entry))
            else:
                try: ss=f"{len(list(entry.iterdir()))} items"
                except: ss="—"
            sl=Gtk.Label(label=ss); sl.set_size_request(90,-1); sl.set_xalign(1); sl.add_css_class("file-meta"); row.append(sl)
            ck=Gtk.GestureClick(); ck.connect("pressed",self._click,entry,row); row.add_controller(ck)
            rc=Gtk.GestureClick(); rc.set_button(3); rc.connect("pressed",self._rclick,entry,row); row.add_controller(rc)
            # v2.0.4: Drag source
            self._setup_drag_source(row, entry)
            # v2.0.4: Drop target on folders
            if entry.is_dir(): self._setup_drop_target(row, entry)
            self.fc.append(row)
            if smooth: GLib.timeout_add(15 * idx, self._fade_in, row)

    def _rgrid(self, entries):
        igs=int(self.S["icon_size_grid"]*self.S["ui_scale"])
        smooth = self.S.get("perf_mode","normal") == "smooth"
        flow=Gtk.FlowBox(); flow.set_valign(Gtk.Align.START); flow.set_max_children_per_line(10)
        flow.set_min_children_per_line(3); flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_homogeneous(True); flow.set_column_spacing(2); flow.set_row_spacing(2)
        flow.set_margin_start(12); flow.set_margin_end(12); self.fc.append(flow)
        for idx, entry in enumerate(entries):
            item=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4); item.add_css_class("grid-item")
            if smooth: item.set_opacity(0)
            item.set_size_request(int(igs*2.2),int(igs*2.2)); item.set_halign(Gtk.Align.CENTER)
            item.append(self._make_icon(entry, igs))
            nl=Gtk.Label(label=entry.name); nl.set_ellipsize(Pango.EllipsizeMode.MIDDLE); nl.set_max_width_chars(14)
            nl.set_lines(2); nl.set_wrap(True); nl.set_justify(Gtk.Justification.CENTER); nl.add_css_class("grid-name"); item.append(nl)
            ck=Gtk.GestureClick(); ck.connect("pressed",self._click,entry,item); item.add_controller(ck)
            rc=Gtk.GestureClick(); rc.set_button(3); rc.connect("pressed",self._rclick,entry,item); item.add_controller(rc)
            # v2.0.4: Drag source
            self._setup_drag_source(item, entry)
            # v2.0.4: Drop target on folders
            if entry.is_dir(): self._setup_drop_target(item, entry)
            flow.append(item)
            if smooth: GLib.timeout_add(20 * idx, self._fade_in, item)

    def _fade_in(self, widget):
        """Smooth mode: animate opacity from 0 to 1"""
        cur = widget.get_opacity()
        if cur < 1.0:
            nxt = min(1.0, cur + 0.15)
            widget.set_opacity(nxt)
            if nxt < 1.0: GLib.timeout_add(16, self._fade_in, widget)
        return False

    # =========================================================
    #                 CLICK + CONTEXT + FILE OPS
    # =========================================================
    def _click(self, g, n, x, y, entry, w):
        if n==1:
            ctrl=bool(g.get_current_event_state()&Gdk.ModifierType.CONTROL_MASK)
            if not ctrl:
                for ww in self.T.sel_w.values(): ww.remove_css_class("selected")
                self.T.sel.clear(); self.T.sel_w={}
            if entry in self.T.sel: self.T.sel.discard(entry); w.remove_css_class("selected"); self.T.sel_w.pop(entry,None)
            else: self.T.sel.add(entry); w.add_css_class("selected"); self.T.sel_w[entry]=w
            if self.T.sel: self.sbar.set_text(f"{len(self.T.sel)} selected")
        elif n==2:
            if entry.is_dir(): self.nav_to(entry)
            else: self._open(entry)

    def _rclick(self, g, n, x, y, entry, w):
        if entry not in self.T.sel:
            for ww in self.T.sel_w.values(): ww.remove_css_class("selected")
            self.T.sel={entry}; self.T.sel_w={entry:w}; w.add_css_class("selected")
        menu=Gio.Menu(); menu.append("Open","win.c-open")
        if not entry.is_dir(): menu.append("Open With...","win.c-openwith")
        if entry.is_dir(): menu.append("Open in Tab","win.c-tab"); menu.append("Terminal","win.c-term")
        s1=Gio.Menu(); s1.append("Cut","win.c-cut"); s1.append("Copy","win.c-copy"); s1.append("Paste","win.c-paste"); menu.append_section(None,s1)
        s_arch=Gio.Menu()
        if self.T.sel: s_arch.append("Compress to ZIP","win.c-compress")
        for item in self.T.sel:
            if item.suffix.lower() in ('.zip','.tar','.gz','.bz2','.xz','.7z','.rar'):
                s_arch.append("Extract Here","win.c-extract"); break
        if entry.is_dir(): s_arch.append("Add to Quick Access","win.c-addqa")
        if s_arch.get_n_items() > 0: menu.append_section(None, s_arch)
        s2=Gio.Menu(); s2.append("Rename","win.c-ren"); s2.append("Trash","win.c-del"); s2.append("Properties","win.c-props"); menu.append_section(None,s2)
        for nm,cb in [("c-open",lambda a,p: (self.nav_to(entry) if entry.is_dir() else self._open(entry))),
            ("c-openwith",lambda a,p: self._open_with(None)),
            ("c-tab",lambda a,p: self._tadd(entry)),("c-term",lambda a,p: self._termAt(entry)),
            ("c-cut",lambda a,p: self._cut(None)),("c-copy",lambda a,p: self._copy(None)),("c-paste",lambda a,p: self._paste(None)),("c-compress",lambda a,p: self._compress(None)),("c-extract",lambda a,p: self._ext(None)),
            ("c-addqa",lambda a,p: self._add_quick_access(entry)),
            ("c-ren",lambda a,p: self._ren(None)),("c-del",lambda a,p: self._del(None)),("c-props",lambda a,p: self._props(None))]:
            if self.lookup_action(nm): self.remove_action(nm)
            a=Gio.SimpleAction.new(nm,None); a.connect("activate",cb); self.add_action(a)
        pop=Gtk.PopoverMenu(); pop.set_menu_model(menu); pop.set_parent(w); pop.set_has_arrow(False); pop.popup()

    def _copy(self, b):
        if self.T.sel: self.clip=list(self.T.sel); self.clip_cut=False; self.sbar.set_text(f"{len(self.clip)} copied")
    def _cut(self, b):
        if self.T.sel: self.clip=list(self.T.sel); self.clip_cut=True; self.sbar.set_text(f"{len(self.clip)} cut")

    def _paste(self, b):
        if self.clip:
            c=0; ops=[]
            for item in self.clip:
                dest=self.T.path/item.name
                if dest.exists():
                    base,ext=dest.stem,dest.suffix; i=1
                    while dest.exists(): dest=self.T.path/f"{base} ({i}){ext}"; i+=1
                try:
                    if self.clip_cut: shutil.move(str(item),str(dest)); ops.append((str(item), str(dest)))
                    elif item.is_dir(): shutil.copytree(str(item),str(dest)); ops.append((str(item), str(dest)))
                    else: shutil.copy2(str(item),str(dest)); ops.append((str(item), str(dest)))
                    c+=1
                except: pass
            if ops: self._record_op("move" if self.clip_cut else "copy", ops)
            if self.clip_cut: self.clip=[]
            self._load(); self.sbar.set_text(f"{c} pasted")
            return
        try:
            clip = Gdk.Display.get_default().get_clipboard()
            clip.read_text_async(None, self._paste_from_system)
        except: pass

    def _paste_from_system(self, clip, result):
        try:
            text = clip.read_text_finish(result)
            if not text: return
            c = 0
            for line in text.strip().split("\n"):
                line = line.strip()
                if line.startswith("file://"):
                    src = Path(urllib.parse.unquote(line[7:]))
                    if not src.exists(): continue
                    dest = self.T.path / src.name
                    if dest.exists():
                        base, ext = dest.stem, dest.suffix; i = 1
                        while dest.exists(): dest = self.T.path / f"{base} ({i}){ext}"; i += 1
                    if src.is_dir(): shutil.copytree(str(src), str(dest))
                    else: shutil.copy2(str(src), str(dest))
                    c += 1
            if c > 0:
                self._load(); self.sbar.set_text(f"{c} pasted from clipboard")
        except: pass

    def _newfld(self, b):
        d=Adw.MessageDialog(transient_for=self); d.set_heading("New Folder"); d.set_body("Name:")
        d.add_response("cancel","Cancel"); d.add_response("create","Create")
        d.set_response_appearance("create",Adw.ResponseAppearance.SUGGESTED)
        e=Gtk.Entry(); e.set_text("New Folder"); e.set_margin_start(24); e.set_margin_end(24); d.set_extra_child(e)
        def do_create(dl, r, ent):
            if r=="create" and ent.get_text().strip():
                fp = self.T.path/ent.get_text().strip()
                fp.mkdir(exist_ok=True)
                self._record_op("new_folder", [("", str(fp))])
                self._load()
            dl.close()
        d.connect("response", do_create, e); d.present()

    def _ren(self, b):
        if len(self.T.sel)!=1: return
        item=list(self.T.sel)[0]
        d=Adw.MessageDialog(transient_for=self); d.set_heading("Rename")
        d.add_response("cancel","Cancel"); d.add_response("rename","Rename")
        d.set_response_appearance("rename",Adw.ResponseAppearance.SUGGESTED)
        e=Gtk.Entry(); e.set_text(item.name); e.set_margin_start(24); e.set_margin_end(24); d.set_extra_child(e)
        def do(dl,r,ent,itm):
            if r=="rename":
                new=ent.get_text().strip()
                if new and new!=itm.name:
                    new_path = self.T.path/new
                    try:
                        itm.rename(new_path)
                        self._record_op("rename", [(str(itm), str(new_path))])
                        self.T.sel.clear(); self._load()
                    except: pass
            dl.close()
        d.connect("response",do,e,item); d.present()

    def _del(self, b):
        if not self.T.sel: return
        trash=Path.home()/".local/share/Trash/files"; trash.mkdir(parents=True,exist_ok=True)
        ops=[]
        for item in list(self.T.sel):
            dest = trash/item.name
            try: shutil.move(str(item),str(dest)); ops.append((str(item), str(dest)))
            except: pass
        if ops: self._record_op("trash", ops)
        self.T.sel.clear(); self.T.sel_w={}; self._load()

    def _clear_trash(self, b):
        d=Adw.MessageDialog(transient_for=self)
        d.set_heading("Clear Trash")
        d.set_body("All of your trash folder will be wiped and you will not be able to recover the data.\n\nAre you sure?")
        d.add_response("cancel","Cancel"); d.add_response("clear","Clear Trash")
        d.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        def on_resp(dlg, resp):
            if resp == "clear":
                trash = Path.home()/".local/share/Trash"
                for sub in ["files","info"]:
                    p = trash/sub
                    if p.exists():
                        for item in p.iterdir():
                            try:
                                if item.is_dir(): shutil.rmtree(str(item))
                                else: item.unlink()
                            except: pass
                self.sbar.set_text("Trash cleared")
                # Refresh if currently viewing trash
                if "Trash" in str(self.T.path): self._load()
            dlg.close()
        d.connect("response", on_resp); d.present()

    def _show_filter_menu(self, b):
        """Show filter popover with type filters"""
        pop = Gtk.Popover(); pop.set_parent(b); pop.set_has_arrow(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8); box.set_margin_bottom(8)
        box.set_margin_start(8); box.set_margin_end(8)
        # Current filter
        cur = getattr(self, '_active_filter', None)
        filters = [
            ("All Files", None),
            ("Images", {'.png','.jpg','.jpeg','.gif','.webp','.bmp','.svg','.ico','.tiff'}),
            ("Documents", {'.pdf','.doc','.docx','.odt','.txt','.md','.rtf','.xls','.xlsx','.pptx','.csv'}),
            ("Videos", {'.mp4','.mkv','.avi','.mov','.webm','.flv','.wmv'}),
            ("Audio", {'.mp3','.flac','.wav','.ogg','.aac','.m4a','.wma'}),
            ("Archives", {'.zip','.tar','.gz','.bz2','.xz','.7z','.rar','.deb','.rpm'}),
            ("Code", {'.py','.js','.ts','.html','.css','.json','.xml','.rs','.go','.c','.cpp','.java','.cs','.rb','.sh'}),
            ("Folders Only", "dirs"),
            ("Hidden Files", "hidden"),
        ]
        for label, filt in filters:
            btn = Gtk.Button(label=label); btn.add_css_class("flat")
            btn.set_halign(Gtk.Align.FILL)
            if cur == filt or (cur is None and filt is None):
                btn.add_css_class("active-tab")
            def apply_filter(b, f=filt, p=pop):
                self._active_filter = f
                p.popdown()
                self._load()
            btn.connect("clicked", apply_filter)
            box.append(btn)
        pop.set_child(box); pop.popup()

    def _compress(self, b):
        """Compress selected files — choose format"""
        if not self.T.sel: return
        items = list(self.T.sel)
        default_name = items[0].stem if len(items) == 1 else self.T.path.name
        d = Adw.MessageDialog(transient_for=self)
        d.set_heading("Compress"); d.set_body("Archive name and format:")
        d.add_response("cancel", "Cancel"); d.add_response("compress", "Compress")
        d.set_response_appearance("compress", Adw.ResponseAppearance.SUGGESTED)
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vb.set_margin_start(24); vb.set_margin_end(24)
        e = Gtk.Entry(); e.set_text(default_name); vb.append(e)
        # Format selector
        fmt_box = Gtk.Box(spacing=6)
        self._compress_fmt = ".zip"
        for ext, label in [(".zip", "ZIP"), (".tar.gz", "TAR.GZ"), (".tar.xz", "TAR.XZ"), (".tar.bz2", "TAR.BZ2")]:
            fb = Gtk.Button(label=label); fb.add_css_class("flat"); fb.add_css_class("theme-btn")
            if ext == ".zip": fb.add_css_class("active")
            def pick_fmt(b, e=ext):
                self._compress_fmt = e
                for c in list(fmt_box): c.remove_css_class("active")
                b.add_css_class("active")
            fb.connect("clicked", pick_fmt); fmt_box.append(fb)
        vb.append(fmt_box)
        d.set_extra_child(vb)
        def do_compress(dlg, resp, entry):
            if resp == "compress":
                name = entry.get_text().strip()
                if not name: dlg.close(); return
                fmt = self._compress_fmt
                if not name.endswith(fmt): name += fmt
                dest = self.T.path / name
                try:
                    if fmt == ".zip":
                        import zipfile
                        with zipfile.ZipFile(str(dest), 'w', zipfile.ZIP_DEFLATED) as zf:
                            for item in items:
                                if item.is_dir():
                                    for root, dirs, files in os.walk(str(item)):
                                        for fn in files:
                                            fp = os.path.join(root, fn)
                                            zf.write(fp, os.path.relpath(fp, str(item.parent)))
                                else:
                                    zf.write(str(item), item.name)
                    else:
                        # tar variants
                        tar_mode = "w:gz" if fmt == ".tar.gz" else "w:xz" if fmt == ".tar.xz" else "w:bz2"
                        import tarfile
                        with tarfile.open(str(dest), tar_mode) as tf:
                            for item in items:
                                tf.add(str(item), arcname=item.name)
                    self._load(); self.sbar.set_text(f"Compressed to {name}")
                except Exception as ex:
                    self.sbar.set_text(f"Compress failed: {ex}")
            dlg.close()
        d.connect("response", do_compress, e); d.present()

    def _ext(self, b):
        """Extract archives — supports zip, tar, 7z, rar"""
        for item in list(self.T.sel):
            ext = item.suffix.lower()
            name = item.name
            # Handle .tar.gz, .tar.xz, .tar.bz2
            if name.endswith('.tar.gz') or name.endswith('.tar.xz') or name.endswith('.tar.bz2'):
                stem = name.rsplit('.tar', 1)[0]
            else:
                stem = item.stem
            dest = self.T.path / stem; dest.mkdir(exist_ok=True)
            try:
                if ext == '.zip':
                    import zipfile
                    with zipfile.ZipFile(str(item)) as z: z.extractall(str(dest))
                elif ext in ('.gz', '.xz', '.bz2') or ext == '.tar':
                    import tarfile
                    with tarfile.open(str(item)) as tf: tf.extractall(str(dest))
                elif ext == '.7z':
                    subprocess.run(['7z', 'x', str(item), f'-o{dest}'], check=True)
                elif ext == '.rar':
                    subprocess.run(['unrar', 'x', str(item), str(dest) + '/'], check=True)
                else:
                    subprocess.run(['tar', 'xf', str(item), '-C', str(dest)], check=True)
                self.sbar.set_text(f"Extracted to {stem}/")
            except Exception as ex:
                self.sbar.set_text(f"Extract failed: {ex}")
        self._load()

    def _selall(self, b):
        try: entries=list(self.T.path.iterdir())
        except: return
        if not self.T.hidden: entries=[e for e in entries if not e.name.startswith('.')]
        self.T.sel=set(entries)
        ch=self.fc.get_first_child()
        while ch: ch.add_css_class("selected"); ch=ch.get_next_sibling()
        self.sbar.set_text(f"{len(entries)} selected")

    def _props(self, b):
        if not self.T.sel: return
        item = list(self.T.sel)[0]
        try: st = item.stat()
        except: return

        d = Adw.MessageDialog(transient_for=self)
        d.set_heading("Properties")
        d.add_response("close", "Close")

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main.set_margin_start(20); main.set_margin_end(20)

        # Icon + Name header
        hdr = Gtk.Box(spacing=12); hdr.set_halign(Gtk.Align.CENTER)
        hdr.set_margin_bottom(8)
        icon_size = 48
        ico = self._make_icon(item, icon_size)
        hdr.append(ico)
        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_lbl = Gtk.Label(label=item.name)
        name_lbl.set_xalign(0); name_lbl.set_selectable(True)
        name_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        name_lbl.set_max_width_chars(35)
        name_lbl.add_css_class("settings-title")
        name_box.append(name_lbl)
        ftype = "Folder" if item.is_dir() else (item.suffix.upper()[1:] + " File" if item.suffix else "File")
        type_lbl = Gtk.Label(label=ftype); type_lbl.set_xalign(0)
        type_lbl.add_css_class("dim-label"); name_box.append(type_lbl)
        hdr.append(name_box)
        main.append(hdr)
        main.append(Gtk.Separator())

        # Info grid
        grid = Gtk.Grid(); grid.set_row_spacing(8); grid.set_column_spacing(16)
        row = 0
        def add_row(key, val):
            nonlocal row
            kl = Gtk.Label(label=key); kl.set_xalign(0); kl.set_opacity(0.6)
            vl = Gtk.Label(label=str(val)); vl.set_xalign(0); vl.set_selectable(True)
            vl.set_ellipsize(Pango.EllipsizeMode.MIDDLE); vl.set_max_width_chars(36)
            grid.attach(kl, 0, row, 1, 1); grid.attach(vl, 1, row, 1, 1)
            row += 1

        add_row("Location", str(item.parent))

        # Size
        if item.is_file():
            size_bytes = st.st_size
            add_row("Size", f"{fmt_bytes(size_bytes)} ({size_bytes:,} bytes)")
        else:
            try:
                files = list(item.rglob('*'))
                file_count = sum(1 for f in files if f.is_file())
                dir_count = sum(1 for f in files if f.is_dir())
                total = sum(f.stat().st_size for f in files if f.is_file())
                add_row("Size", f"{fmt_bytes(total)} ({total:,} bytes)")
                add_row("Contains", f"{file_count} files, {dir_count} folders")
            except:
                add_row("Size", "Unknown")

        # Dates
        add_row("Modified", datetime.fromtimestamp(st.st_mtime).strftime("%d %b %Y, %I:%M:%S %p"))
        add_row("Accessed", datetime.fromtimestamp(st.st_atime).strftime("%d %b %Y, %I:%M:%S %p"))
        try:
            add_row("Created", datetime.fromtimestamp(st.st_ctime).strftime("%d %b %Y, %I:%M:%S %p"))
        except: pass

        # Owner/Group
        try:
            import pwd, grp
            add_row("Owner", pwd.getpwuid(st.st_uid).pw_name)
            add_row("Group", grp.getgrgid(st.st_gid).gr_name)
        except: pass

        # MIME type for files
        if item.is_file():
            try:
                import subprocess as sp
                mime = sp.run(["file", "--mime-type", "-b", str(item)], capture_output=True, text=True, timeout=2).stdout.strip()
                add_row("MIME Type", mime)
            except: pass

        main.append(grid)
        main.append(Gtk.Separator())

        # Permissions section
        perm_label = Gtk.Label(label="Permissions"); perm_label.set_xalign(0)
        perm_label.add_css_class("settings-section"); main.append(perm_label)
        perm_grid = Gtk.Grid(); perm_grid.set_row_spacing(4); perm_grid.set_column_spacing(12)
        mode = st.st_mode
        headers = ["", "Read", "Write", "Execute"]
        for c, h in enumerate(headers):
            hl = Gtk.Label(label=h); hl.set_opacity(0.6 if c > 0 else 1.0)
            perm_grid.attach(hl, c, 0, 1, 1)
        for r, (label, shift) in enumerate([("Owner", 6), ("Group", 3), ("Others", 0)], 1):
            rl = Gtk.Label(label=label); rl.set_xalign(0)
            perm_grid.attach(rl, 0, r, 1, 1)
            for bit_off, col in [(2, 1), (1, 2), (0, 3)]:
                cb = Gtk.CheckButton()
                cb.set_active(bool(mode & (1 << (shift + bit_off))))
                cb.set_halign(Gtk.Align.CENTER)
                cb.set_sensitive(os.access(str(item), os.W_OK))
                def on_perm_toggle(btn, s=shift, bo=bit_off, it=item):
                    try:
                        cur = it.stat().st_mode
                        if btn.get_active(): cur |= (1 << (s + bo))
                        else: cur &= ~(1 << (s + bo))
                        os.chmod(str(it), cur)
                    except: btn.set_active(not btn.get_active())
                cb.connect("toggled", on_perm_toggle)
                perm_grid.attach(cb, col, r, 1, 1)
        main.append(perm_grid)

        # Octal display
        octal_str = oct(mode)[-3:]
        octal_lbl = Gtk.Label(label=f"Octal: {octal_str}"); octal_lbl.set_xalign(0)
        octal_lbl.set_opacity(0.5); octal_lbl.set_selectable(True)
        main.append(octal_lbl)

        d.set_extra_child(main)
        d.connect("response", lambda dl, r: dl.close())
        d.present()

    def _quick_look(self):
        """Spacebar Quick Look - centered popup preview"""
        if not self.T.sel: return
        item = list(self.T.sel)[0]
        if getattr(self, '_ql_win', None):
            self._ql_close()
            return
        # Create popup window
        self._ql_win = Gtk.Window(transient_for=self, modal=True, decorated=False)
        self._ql_win.set_default_size(620, 500)
        # Close on click outside or Escape
        ck = Gtk.GestureClick(); ck.connect("pressed", lambda g,n,x,y: self._ql_close())
        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed", self._ql_key)
        self._ql_win.add_controller(kc)
        # Outer box with rounded corners
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.add_css_class("ql-box")
        prov = Gtk.CssProvider()
        is_dark = not self.S.get("light_mode", False)
        bg = "rgba(40,40,40,0.95)" if is_dark else "rgba(255,255,255,0.97)"
        fg = "rgba(255,255,255,0.9)" if is_dark else "rgba(0,0,0,0.85)"
        border = "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.12)"
        prov.load_from_data(f".ql-box {{ background: {bg}; border-radius: 12px; border: 1px solid {border}; padding: 0; }} .ql-title {{ color: {fg}; font-weight: 600; font-size: 14px; }} .ql-info {{ color: {fg}; opacity: 0.6; font-size: 12px; }}".encode())
        outer.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # Header bar with filename + close button
        hdr = Gtk.Box(spacing=8)
        hdr.set_margin_start(16); hdr.set_margin_end(8); hdr.set_margin_top(12); hdr.set_margin_bottom(8)
        title = Gtk.Label(label=item.name); title.add_css_class("ql-title")
        title.set_ellipsize(Pango.EllipsizeMode.MIDDLE); title.set_hexpand(True); title.set_xalign(0)
        title.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        hdr.append(title)
        close_btn = Gtk.Button(icon_name="window-close-symbolic")
        close_btn.add_css_class("flat"); close_btn.connect("clicked", lambda b: self._ql_close())
        hdr.append(close_btn)
        outer.append(hdr)
        # Separator
        sep = Gtk.Separator(); outer.append(sep)
        # Content area
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.set_vexpand(True); content.set_margin_start(16); content.set_margin_end(16)
        content.set_margin_top(12); content.set_margin_bottom(12)
        ext = item.suffix.lower() if item.is_file() else ""
        if item.is_dir():
            self._ql_dir(content, item, prov)
        elif ext in ('.png','.jpg','.jpeg','.gif','.webp','.bmp','.svg','.ico','.tiff','.tif'):
            self._ql_image(content, item)
        elif ext in ('.txt','.md','.py','.js','.ts','.html','.css','.json','.xml','.yaml','.yml',
                      '.toml','.ini','.cfg','.conf','.sh','.bash','.zsh','.fish','.rs','.go','.c',
                      '.cpp','.h','.hpp','.java','.kt','.cs','.rb','.lua','.r','.sql','.csv','.log',
                      '.gitignore','.env','.dockerfile',''):
            self._ql_text(content, item, prov)
        elif ext in ('.pdf',):
            self._ql_pdf_info(content, item, prov)
        else:
            self._ql_generic(content, item, prov)
        outer.append(content)
        # Footer with file info
        self._ql_footer(outer, item, prov)
        self._ql_win.set_child(outer)
        self._ql_win.present()

    def _ql_image(self, box, item):
        """Preview image file"""
        try:
            pic = Gtk.Picture.new_for_filename(str(item))
            pic.set_can_shrink(True); pic.set_vexpand(True)
            pic.set_content_fit(Gtk.ContentFit.CONTAIN)
            box.append(pic)
        except:
            lbl = Gtk.Label(label="Cannot preview image"); lbl.set_vexpand(True)
            box.append(lbl)

    def _ql_text(self, box, item, prov):
        """Preview text file"""
        try:
            with open(str(item), 'r', errors='replace') as f:
                text = f.read(8192)  # First 8KB
            if len(text) >= 8192: text += "\n\n... (truncated)"
            sw = Gtk.ScrolledWindow(); sw.set_vexpand(True)
            tv = Gtk.TextView(); tv.set_editable(False); tv.set_cursor_visible(False)
            tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR); tv.set_monospace(True)
            tv.get_buffer().set_text(text)
            tv.set_margin_start(4); tv.set_margin_end(4)
            sw.set_child(tv); box.append(sw)
        except:
            lbl = Gtk.Label(label="Cannot read file"); lbl.set_vexpand(True)
            box.append(lbl)

    def _ql_dir(self, box, item, prov):
        """Preview directory contents"""
        try:
            entries = sorted(list(item.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))[:20]
            sw = Gtk.ScrolledWindow(); sw.set_vexpand(True)
            lb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for e in entries:
                row = Gtk.Box(spacing=8); row.set_margin_start(4); row.set_margin_top(2)
                icon_name = "folder-symbolic" if e.is_dir() else "text-x-generic-symbolic"
                ic = Gtk.Image.new_from_icon_name(icon_name); ic.set_pixel_size(16)
                row.append(ic)
                nl = Gtk.Label(label=e.name); nl.set_xalign(0)
                nl.set_ellipsize(Pango.EllipsizeMode.END); nl.add_css_class("ql-info")
                nl.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                row.append(nl); lb.append(row)
            if len(list(item.iterdir())) > 20:
                more = Gtk.Label(label=f"... and {len(list(item.iterdir())) - 20} more")
                more.add_css_class("ql-info"); more.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                lb.append(more)
            sw.set_child(lb); box.append(sw)
        except:
            lbl = Gtk.Label(label="Cannot read directory"); lbl.set_vexpand(True)
            box.append(lbl)

    def _ql_pdf_info(self, box, item, prov):
        """PDF info preview"""
        ic = Gtk.Image.new_from_icon_name("x-office-document-symbolic")
        ic.set_pixel_size(64); ic.set_vexpand(True); ic.set_valign(Gtk.Align.CENTER)
        box.append(ic)
        lbl = Gtk.Label(label="PDF Document"); lbl.add_css_class("ql-info")
        lbl.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        box.append(lbl)

    def _ql_generic(self, box, item, prov):
        """Generic file preview with icon"""
        ic = Gtk.Image.new_from_icon_name("text-x-generic-symbolic")
        ic.set_pixel_size(64); ic.set_vexpand(True); ic.set_valign(Gtk.Align.CENTER)
        box.append(ic)

    def _ql_footer(self, outer, item, prov):
        """File info footer"""
        sep = Gtk.Separator(); outer.append(sep)
        footer = Gtk.Box(spacing=16)
        footer.set_margin_start(16); footer.set_margin_end(16)
        footer.set_margin_top(8); footer.set_margin_bottom(10)
        try:
            st = item.stat()
            ftype = "Folder" if item.is_dir() else (item.suffix.upper()[1:] + " File" if item.suffix else "File")
            size = fmt_bytes(st.st_size) if item.is_file() else ""
            mod = datetime.fromtimestamp(st.st_mtime).strftime("%d %b %Y, %I:%M %p")
            info_parts = [ftype]
            if size: info_parts.append(size)
            info_parts.append(mod)
            info_str = "  ·  ".join(info_parts)
        except:
            info_str = ""
        il = Gtk.Label(label=info_str); il.add_css_class("ql-info")
        il.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        il.set_hexpand(True); il.set_xalign(0)
        footer.append(il)
        # Open button
        open_btn = Gtk.Button(label="Open")
        open_btn.add_css_class("suggested-action")
        open_btn.connect("clicked", lambda b: (self._ql_close(), self._open(item)))
        footer.append(open_btn)
        outer.append(footer)

    def _ql_key(self, ctrl, kv, kc, state):
        if kv in (Gdk.KEY_Escape, Gdk.KEY_space):
            self._ql_close(); return True
        return False

    def _ql_close(self):
        if getattr(self, '_ql_win', None):
            self._ql_win.close()
            self._ql_win = None

    def _term(self, b): self._termAt(self.T.path)
    def _termAt(self, p):
        pp=str(p) if p.is_dir() else str(p.parent)
        for t in ['ptyxis','gnome-terminal','konsole','xterm']:
            try: subprocess.Popen([t],cwd=pp); return
            except: continue

    def _thid(self, b): self.T.hidden=not self.T.hidden; self._load()

    def _toggle_split(self, b=None):
        """Toggle split view - creates a new tab and shows both side by side"""
        self._split_active = not self._split_active
        if self._split_active:
            # Create new tab for right pane
            self._tadd(self.T.path)
            self._split_left_tab = self.atab - 1  # Original tab
            self._split_right_tab = self.atab      # New tab
            # Replace scroll with paned
            self.mbox.remove(self.scroll)
            self._split_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
            self._split_paned.set_vexpand(True)
            self._split_paned.set_wide_handle(True)
            # Left pane - original scroll + fc
            self._split_paned.set_start_child(self.scroll)
            self.scroll.set_hexpand(True)
            # Right pane - new scroll + fc
            self._split_scroll2 = Gtk.ScrolledWindow(); self._split_scroll2.set_vexpand(True)
            self._split_scroll2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            self._split_scroll2.set_hexpand(True)
            self._split_fc2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self._split_fc2.set_margin_top(2); self._split_fc2.set_margin_bottom(8)
            self._split_fc2.set_valign(Gtk.Align.START)
            vp2 = Gtk.Viewport(); vp2.set_child(self._split_fc2)
            vp2.set_vscroll_policy(Gtk.ScrollablePolicy.MINIMUM)
            self._split_scroll2.set_child(vp2)
            # Right side container with its own breadcrumb
            right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self._split_bc2 = Gtk.Box(spacing=0)
            self._split_bc2.set_margin_start(8); self._split_bc2.set_margin_top(4); self._split_bc2.set_margin_bottom(4)
            right_box.append(self._split_bc2)
            right_box.append(Gtk.Separator())
            right_box.append(self._split_scroll2)
            self._split_right_box = right_box
            self._split_paned.set_end_child(right_box)
            # Insert paned where scroll was (before sbar)
            # Find sbar position and insert before it
            self.mbox.insert_child_after(self._split_paned, self.colhdr)
            self._split_paned.set_position(self.get_width() // 2 - 100)
            # Click handlers to switch focus between panes
            lck = Gtk.GestureClick(); lck.connect("pressed", lambda g,n,x,y: self._split_set_focus(False))
            self.scroll.add_controller(lck)
            rck = Gtk.GestureClick(); rck.connect("pressed", lambda g,n,x,y: self._split_set_focus(True))
            self._split_right_box.add_controller(rck)
            # Drop target on entire right pane (drop files into right directory)
            self._setup_split_drop(self._split_scroll2)
            # Drop target on left pane scroll to accept from right
            self._setup_left_pane_drop()
            # Start with left focused
            self._split_focus_right = False
            self.scroll.set_opacity(1.0)
            self._split_right_box.set_opacity(0.5)
            self.atab = self._split_left_tab
            self._tref(); self.nav_to(self.T.path, push=False)
            self._load_split_right()
            self._update_split_bc()
        else:
            # Close split - remove right tab and restore layout
            self._split_focus_right = False
            self.scroll.set_opacity(1.0)
            if hasattr(self, '_split_paned') and self._split_paned:
                self._split_paned.set_start_child(None)
                self.mbox.remove(self._split_paned)
                self.mbox.insert_child_after(self.scroll, self.colhdr)
                self._split_paned = None
            # Remove the split tab
            if hasattr(self, '_split_right_tab'):
                if self._split_right_tab < len(self.tabs):
                    self.tabs.pop(self._split_right_tab)
                    if self.atab >= len(self.tabs): self.atab = len(self.tabs) - 1
            self._tref(); self.nav_to(self.T.path, push=False)

    def _load_split_right(self):
        """Load right split pane with its tab's content"""
        if not hasattr(self, '_split_fc2'): return
        self._clr(self._split_fc2)
        if self._split_right_tab >= len(self.tabs): return
        t = self.tabs[self._split_right_tab]
        try: entries = list(t.path.iterdir())
        except PermissionError:
            l = Gtk.Label(label="Permission denied"); l.add_css_class("empty-state"); l.set_vexpand(True)
            self._split_fc2.append(l); return
        if not t.hidden: entries = [e for e in entries if not e.name.startswith('.')]
        entries = self._sort(entries)
        if not entries:
            l = Gtk.Label(label="Empty folder"); l.add_css_class("empty-state"); l.set_vexpand(True)
            self._split_fc2.append(l); return
        ils = int(self.S["icon_size_list"] * self.S["ui_scale"])
        for entry in entries:
            row = Gtk.Box(spacing=12); row.add_css_class("file-row")
            row.append(self._make_icon(entry, ils))
            nl = Gtk.Label(label=entry.name); nl.set_xalign(0); nl.set_hexpand(True)
            nl.set_ellipsize(Pango.EllipsizeMode.MIDDLE); nl.add_css_class("file-name"); row.append(nl)
            ml = Gtk.Label(label=self._ft(self._mt(entry))); ml.set_size_request(140, -1)
            ml.set_xalign(1); ml.add_css_class("file-meta"); row.append(ml)
            ck = Gtk.GestureClick()
            ck.connect("pressed", self._split_right_click, entry, row)
            row.add_controller(ck)
            self._setup_split_drag(row, entry)
            if entry.is_dir(): self._setup_split_drop(row, entry)
            self._split_fc2.append(row)

    def _setup_split_drag(self, widget, entry):
        """Drag source for right split pane — uses right tab's selection"""
        drag = Gtk.DragSource()
        drag.set_actions(Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        def on_prepare(src, x, y):
            t = self.tabs[self._split_right_tab]
            if entry in t.sel and len(t.sel) > 1:
                self._drag_paths = [str(e) for e in t.sel]
            else:
                self._drag_paths = [str(entry)]
            uris = ["file://" + urllib.parse.quote(p) for p in self._drag_paths]
            return Gdk.ContentProvider.new_for_value(GObject.Value(str, "\n".join(uris)))
        def on_begin(src, drag_obj):
            cnt = len(self._drag_paths)
            label = f"{cnt} items" if cnt > 1 else Path(self._drag_paths[0]).name
            snap = Gtk.DragIcon.get_for_drag(drag_obj)
            lbl = Gtk.Label(label=f"  {label}  "); lbl.add_css_class("file-name")
            snap.set_child(lbl)
        drag.connect("prepare", on_prepare)
        drag.connect("drag-begin", on_begin)
        widget.add_controller(drag)

    def _setup_split_drop(self, widget, dest_entry=None):
        """Drop target for right split pane — refreshes both panes"""
        dest_path = dest_entry if dest_entry else None
        drop = Gtk.DropTarget.new(str, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        def on_enter(target, x, y):
            widget.add_css_class("drop-highlight")
            return Gdk.DragAction.MOVE
        def on_leave(target):
            widget.remove_css_class("drop-highlight")
        def on_drop(target, value, x, y):
            widget.remove_css_class("drop-highlight")
            actual_dest = dest_path if dest_path else self.tabs[self._split_right_tab].path
            if not actual_dest.exists() or not actual_dest.is_dir(): return False
            paths = value.split("\n")
            moved = 0
            for ps in paths:
                ps = ps.strip()
                if not ps: continue
                if ps.startswith("file://"): ps = urllib.parse.unquote(ps[7:])
                src = Path(ps)
                if not src.exists(): continue
                if src == actual_dest or src.parent == actual_dest: continue
                dst = actual_dest / src.name
                if dst.exists():
                    base, ext = dst.stem, dst.suffix; i=1
                    while dst.exists(): dst = actual_dest / f"{base} ({i}){ext}"; i+=1
                try: shutil.move(str(src), str(dst)); moved += 1
                except: pass
            if moved:
                self._load()  # Refresh left pane
                self._load_split_right()  # Refresh right pane
                self.sbar.set_text(f"Moved {moved} item{'s' if moved>1 else ''}")
            return True
        drop.connect("enter", on_enter)
        drop.connect("leave", on_leave)
        drop.connect("drop", on_drop)
        widget.add_controller(drop)

    def _setup_left_pane_drop(self):
        """Add drop target on left pane that refreshes both sides after drop"""
        drop = Gtk.DropTarget.new(str, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        def on_enter(target, x, y):
            return Gdk.DragAction.MOVE
        def on_drop(target, value, x, y):
            actual_dest = self.tabs[self._split_left_tab].path
            if not actual_dest.exists() or not actual_dest.is_dir(): return False
            paths = value.split("\n")
            moved = 0
            for ps in paths:
                ps = ps.strip()
                if not ps: continue
                if ps.startswith("file://"): ps = urllib.parse.unquote(ps[7:])
                src = Path(ps)
                if not src.exists(): continue
                if src == actual_dest or src.parent == actual_dest: continue
                dst = actual_dest / src.name
                if dst.exists():
                    base, ext = dst.stem, dst.suffix; i=1
                    while dst.exists(): dst = actual_dest / f"{base} ({i}){ext}"; i+=1
                try: shutil.move(str(src), str(dst)); moved += 1
                except: pass
            if moved:
                self._load()
                self._load_split_right()
                self.sbar.set_text(f"Moved {moved} item{'s' if moved>1 else ''}")
            return True
        drop.connect("enter", on_enter)
        drop.connect("drop", on_drop)
        self.scroll.add_controller(drop)

    def _split_right_click(self, g, n, x, y, entry, w):
        """Handle clicks in right split pane"""
        if n == 1:
            for child in list(self._split_fc2):
                if hasattr(child, 'get_css_classes') and 'selected' in child.get_css_classes():
                    child.remove_css_class("selected")
            w.add_css_class("selected")
            self.tabs[self._split_right_tab].sel = {entry}
        elif n == 2:
            if entry.is_dir():
                self.tabs[self._split_right_tab].path = entry
                self.tabs[self._split_right_tab].sel.clear()
                self._load_split_right()
                self._update_split_bc()
                self._tref()
            else:
                self._open(entry)

    def _split_set_focus(self, right):
        """Switch which split pane is active - skip during drag"""
        if self._drag_paths: return  # Don't change focus while dragging
        if self._split_focus_right == right: return
        self._split_focus_right = right
        if right:
            self.atab = self._split_right_tab
            self.scroll.set_opacity(0.5)
            self._split_right_box.set_opacity(1.0)
        else:
            self.atab = self._split_left_tab
            self.scroll.set_opacity(1.0)
            self._split_right_box.set_opacity(0.5)
        self._tref()
        self._upd_bc()

    def _update_split_bc(self):
        """Update breadcrumb for right split pane"""
        if not hasattr(self, '_split_bc2'): return
        self._clr(self._split_bc2)
        if self._split_right_tab >= len(self.tabs): return
        t = self.tabs[self._split_right_tab]
        parts = t.path.parts
        for i, part in enumerate(parts):
            if i > 0:
                s = Gtk.Label(label="›"); s.add_css_class("path-sep"); self._split_bc2.append(s)
            name = part if part != "/" else "Filesystem"
            btn = Gtk.Button(label=name); btn.add_css_class("path-btn"); btn.add_css_class("flat")
            if i == len(parts) - 1: btn.add_css_class("path-current")
            target = Path(*parts[:i+1]) if i > 0 else Path("/")
            def nav_right(b, p=target):
                self.tabs[self._split_right_tab].path = p
                self.tabs[self._split_right_tab].sel.clear()
                self._load_split_right()
                self._update_split_bc()
                self._tref()
            btn.connect("clicked", nav_right)
            self._split_bc2.append(btn)

    def _open(self, p):
        add_recent(p)  # v2.8.2: track recent files
        try: Gtk.FileLauncher.new(Gio.File.new_for_path(str(p))).launch(self,None,None)
        except: subprocess.Popen(['xdg-open',str(p)])

    def on_back(self, *a):
        if self.T.hi>0:
            self.T.hi-=1; self.T.path=self.T.hist[self.T.hi]; self.T.sel.clear(); self.T.sel_w={}
            self._upd_nav(); self._upd_bc(); self._upd_sb(); self._tref(); self._load()

    def on_fwd(self, *a):
        if self.T.hi<len(self.T.hist)-1:
            self.T.hi+=1; self.T.path=self.T.hist[self.T.hi]; self.T.sel.clear(); self.T.sel_w={}
            self._upd_nav(); self._upd_bc(); self._upd_sb(); self._tref(); self._load()

    def _upd_nav(self): self.bbk.set_sensitive(self.T.hi>0); self.bfw.set_sensitive(self.T.hi<len(self.T.hist)-1)

    def _addr_edit_start(self, gesture, n, x, y):
        """Switch breadcrumb to editable text entry"""
        if getattr(self, '_addr_editing', False): return
        widget = self.bcrumb_wrap.pick(x, y, Gtk.PickFlags.DEFAULT)
        if widget and (isinstance(widget, Gtk.Button) or (widget.get_parent() and isinstance(widget.get_parent(), Gtk.Button))):
            return
        self._addr_editing = True
        self.bcrumb.set_visible(False)
        self.addr_entry.set_visible(True)
        self.addr_entry.set_text(str(self.T.path))
        GLib.timeout_add(50, self._addr_grab_focus)

    def _addr_grab_focus(self):
        self.addr_entry.grab_focus()
        self.addr_entry.select_region(0, -1)

    def _addr_edit_cancel(self):
        """Cancel address editing, show breadcrumb again"""
        if not getattr(self, '_addr_editing', False): return
        self._addr_editing = False
        self.addr_entry.set_visible(False)
        self.bcrumb.set_visible(True)

    def _addr_activate(self, entry):
        """Navigate to typed path on Enter - case insensitive"""
        raw = entry.get_text().strip()
        path = Path(raw).expanduser()
        # Try exact match first
        if path.is_dir():
            self._addr_edit_cancel()
            self.nav_to(path)
            return
        # Case-insensitive resolution: walk each path component
        resolved = self._resolve_path_ci(raw)
        if resolved and resolved.is_dir():
            self._addr_edit_cancel()
            self.nav_to(resolved)
            return
        # Try as file - navigate to parent
        if path.is_file():
            self._addr_edit_cancel()
            self.nav_to(path.parent)
            return
        entry.add_css_class("error")
        GLib.timeout_add(1000, lambda: entry.remove_css_class("error"))

    def _resolve_path_ci(self, raw):
        """Resolve path with case-insensitive matching"""
        raw = raw.strip()
        if raw.startswith("~"):
            raw = str(Path.home()) + raw[1:]
        if not raw.startswith("/"): return None
        current = Path("/")
        parts = [p for p in raw.split("/") if p]
        for part in parts:
            # Try exact match first
            exact = current / part
            if exact.exists():
                current = exact
                continue
            # Case-insensitive search in current dir
            try:
                found = False
                for child in current.iterdir():
                    if child.name.lower() == part.lower():
                        current = child
                        found = True
                        break
                if not found:
                    return None
            except (PermissionError, OSError):
                return None
        return current

    def _addr_key(self, ctrl, keyval, keycode, state):
        """Handle Escape to cancel editing"""
        if keyval == Gdk.KEY_Escape:
            self._addr_edit_cancel()
            return True
        return False


    def _upd_bc(self):
        # Cancel address edit if active
        if getattr(self, '_addr_editing', False):
            self._addr_edit_cancel()
        self._clr(self.bcrumb); parts=self.T.path.parts
        for i,part in enumerate(parts):
            if i>0: s=Gtk.Label(label="›"); s.add_css_class("path-sep"); self.bcrumb.append(s)
            name=part if part!="/" else "Filesystem"
            b=Gtk.Button(label=name); b.add_css_class("path-btn"); b.add_css_class("flat")
            if i==len(parts)-1: b.add_css_class("path-current")
            target=Path(*parts[:i+1]) if i>0 else Path("/")
            b.connect("clicked",lambda b,p=target: self.nav_to(p)); self.bcrumb.append(b)
        # v2.1.0: Update Win11 search placeholder with current folder
        if hasattr(self, 'topbar_search') and self.topbar_search:
            folder_name = self.T.path.name or "Home"
            self.topbar_search.set_placeholder_text(f"Search {folder_name}")

    def on_search(self, entry):
        q=entry.get_text().lower().strip()
        if not q: self._load(); return
        try: entries=list(self.T.path.iterdir())
        except: return
        if not self.T.hidden: entries=[e for e in entries if not e.name.startswith('.')]
        entries=[e for e in entries if q in e.name.lower()]; entries=self._sort(entries)
        self._clr(self.fc)
        if self.vmode=="list": self._rlist(entries)
        else: self._rgrid(entries)
        self.sbar.set_text(f"{len(entries)} results")

    def on_vtog(self, b):
        if self.vmode=="list": self.vmode="grid"; b.set_icon_name("view-list-symbolic")
        else: self.vmode="list"; b.set_icon_name("view-grid-symbolic")
        self._load()

    def _keys(self):
        # Capture phase handler for Space (before buttons consume it)
        cap=Gtk.EventControllerKey(); cap.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        cap.connect("key-pressed",self._key_capture); self.add_controller(cap)
        c=Gtk.EventControllerKey(); c.connect("key-pressed",self._key); self.add_controller(c)
    def _key_capture(self, ctrl, kv, kc, state):
        """Capture Space before buttons can consume it, and handle keybind recording"""
        # Handle keybind recording
        if getattr(self, '_rebind_action', None):
            return self._handle_rebind(kv, state)
        if kv==Gdk.KEY_space and self.T.sel and not getattr(self, '_addr_editing', False):
            focus = self.get_focus()
            if focus and (isinstance(focus, Gtk.Entry) or isinstance(focus, Gtk.TextView) or isinstance(focus, Gtk.SearchEntry)):
                return False
            self._quick_look(); return True
        return False
    def _key(self, ctrl, kv, kc, state):
        c=bool(state&Gdk.ModifierType.CONTROL_MASK); sh=bool(state&Gdk.ModifierType.SHIFT_MASK)
        a=bool(state&Gdk.ModifierType.ALT_MASK)
        if kv==Gdk.KEY_BackSpace or (a and kv==Gdk.KEY_Left): self.on_back(); return True
        if a and kv==Gdk.KEY_Right: self.on_fwd(); return True
        if c and kv==Gdk.KEY_f:
            if sh: self._ss_toggle()
            else: self.search.grab_focus()
            return True
        if c and kv==Gdk.KEY_h: self.T.hidden=not self.T.hidden; self._load(); return True
        if c and kv==Gdk.KEY_c: self._copy(None); return True
        if c and kv==Gdk.KEY_x: self._cut(None); return True
        if c and kv==Gdk.KEY_v: self._paste(None); return True
        if c and kv==Gdk.KEY_a: self._selall(None); return True
        if c and kv==Gdk.KEY_n: self._newfld(None); return True
        if c and kv==Gdk.KEY_z and not sh: self._undo(None); return True
        if c and kv==Gdk.KEY_y: self._redo(None); return True
        if c and kv==Gdk.KEY_t: self._tadd(); return True
        if c and kv==Gdk.KEY_w: self._tcls(self.atab); return True
        if kv==Gdk.KEY_Delete: self._del(None); return True
        if c and sh and kv==Gdk.KEY_z: self._compress(None); return True
        if kv==Gdk.KEY_F2 and len(self.T.sel)==1: self._ren(None); return True
        if kv==Gdk.KEY_F5: self._apply_css(); self._load(); return True
        if c and kv==Gdk.KEY_i: self._props(None); return True
        if c and kv==Gdk.KEY_backslash: self._toggle_split(); return True
        if kv==Gdk.KEY_Escape and self.ss_rev.get_reveal_child(): self.ss_rev.set_reveal_child(False); return True
        if kv==Gdk.KEY_Escape and getattr(self, '_ql_win', None): self._ql_close(); return True
        return False

    # =========================================================
    #                 UTILITIES
    # =========================================================
    def _sys_icon(self, p):
        if p.is_dir():
            m={'documents':'folder-documents-symbolic','downloads':'folder-download-symbolic',
                'music':'folder-music-symbolic','pictures':'folder-pictures-symbolic',
                'videos':'folder-videos-symbolic','games':'folder-games-symbolic'}
            return m.get(p.name.lower(),'folder-symbolic')
        m={'.py':'text-x-python-symbolic','.js':'text-x-script-symbolic','.sh':'text-x-script-symbolic',
            '.html':'text-html-symbolic','.pdf':'x-office-document-symbolic','.doc':'x-office-document-symbolic',
            '.docx':'x-office-document-symbolic','.png':'image-x-generic-symbolic','.jpg':'image-x-generic-symbolic',
            '.jpeg':'image-x-generic-symbolic','.gif':'image-x-generic-symbolic','.svg':'image-x-generic-symbolic',
            '.mp3':'audio-x-generic-symbolic','.flac':'audio-x-generic-symbolic','.wav':'audio-x-generic-symbolic',
            '.mp4':'video-x-generic-symbolic','.mkv':'video-x-generic-symbolic','.avi':'video-x-generic-symbolic',
            '.webm':'video-x-generic-symbolic','.mov':'video-x-generic-symbolic',
            '.zip':'package-x-generic-symbolic','.tar':'package-x-generic-symbolic','.gz':'package-x-generic-symbolic',
            '.7z':'package-x-generic-symbolic','.rar':'package-x-generic-symbolic',
            '.iso':'media-optical-symbolic','.appimage':'application-x-executable-symbolic',
            '.txt':'text-x-generic-symbolic','.md':'text-x-generic-symbolic','.log':'text-x-generic-symbolic',
            '.exe':'application-x-executable-symbolic',
            '.c':'text-x-csrc-symbolic','.cpp':'text-x-csrc-symbolic','.rs':'text-x-script-symbolic'}
        return m.get(p.suffix.lower(),'text-x-generic-symbolic')

    def _mt(self, p):
        try: return p.stat().st_mtime
        except: return 0
    def _sz(self, p):
        try: return p.stat().st_size
        except: return 0
    def _ft(self, ts):
        if ts==0: return "—"
        dt=datetime.fromtimestamp(ts); now=datetime.now()
        if dt.date()==now.date(): return f"Today, {dt.strftime('%I:%M %p')}"
        if (now-dt).days<7: return dt.strftime("%a, %I:%M %p")
        return dt.strftime("%d %b %Y, %I:%M %p")

if __name__ == '__main__':
    NovaApp().run(None)
