"""Capture authentic, live screenshots of CheckSense Streamlit app using Chrome WebDriver."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = REPO_ROOT / "reports" / "figures"
TEMP_SHOTS_DIR = REPO_ROOT / "reports" / "figures" / "raw_screenshots"
TEMP_SHOTS_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8670


def run():
    print(f"[*] Starting Streamlit on port {PORT}...")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app/streamlit_app.py",
            "--server.headless=true",
            f"--server.port={PORT}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(REPO_ROOT),
    )

    import urllib.request
    print("[*] Waiting for Streamlit server...")
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"http://localhost:{PORT}/_stcore/health", timeout=2) as resp:
                if resp.status == 200:
                    print("[+] Streamlit is ready!")
                    break
        except Exception:
            time.sleep(1)

    time.sleep(2)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1500,1050")
    options.add_argument("--disable-gpu")
    options.add_argument("--hide-scrollbars")

    driver = webdriver.Chrome(options=options)

    try:
        url = f"http://localhost:{PORT}/?demo=true"
        print(f"[*] Loading live CheckSense Studio: {url}")
        driver.get(url)

        print("[*] Waiting for CheckSense UI to become visible...")
        wait = WebDriverWait(driver, 35)
        wait.until(EC.visibility_of_element_located((By.XPATH, "//h1[contains(., 'CheckSense')]")))
        print("[+] CheckSense header is visible!")

        # Wait for Section A to render
        time.sleep(6)

        # -------------------------------------------------------------
        # Panel A: Document Overview
        # -------------------------------------------------------------
        el_a = driver.find_element(By.XPATH, "//*[contains(text(), 'A. Document Overview')]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'start'});", el_a)
        time.sleep(2)
        shot_a = TEMP_SHOTS_DIR / "actual_panel_a_overview.png"
        driver.save_screenshot(str(shot_a))
        print(f"[+] Saved Panel A: {shot_a} ({shot_a.stat().st_size:,} bytes)")

        # -------------------------------------------------------------
        # Panel B: Requirement Explorer
        # -------------------------------------------------------------
        el_b = driver.find_element(By.XPATH, "//*[contains(text(), 'B. Requirement Explorer')]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'start'});", el_b)
        time.sleep(2)
        shot_b = TEMP_SHOTS_DIR / "actual_panel_b_explorer.png"
        driver.save_screenshot(str(shot_b))
        print(f"[+] Saved Panel B: {shot_b} ({shot_b.stat().st_size:,} bytes)")

        # -------------------------------------------------------------
        # Panel C: Clarification Workspace
        # -------------------------------------------------------------
        el_c = driver.find_element(By.XPATH, "//*[contains(text(), 'C. Clarification Workspace')]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'start'});", el_c)
        time.sleep(2)
        shot_c = TEMP_SHOTS_DIR / "actual_panel_c_clarification.png"
        driver.save_screenshot(str(shot_c))
        print(f"[+] Saved Panel C: {shot_c} ({shot_c.stat().st_size:,} bytes)")

        # -------------------------------------------------------------
        # Panel D: Single Requirement Analysis & Governed Refinement
        # -------------------------------------------------------------
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        top_tabs = driver.find_elements(By.XPATH, "//button[@role='tab'] | //button")
        for b in top_tabs:
            txt = (b.text or b.get_attribute("innerText") or "").strip()
            if "Single Requirement" in txt:
                print(f"[*] Clicking Single Requirement Tab: '{txt}'")
                driver.execute_script("arguments[0].click();", b)
                time.sleep(3)
                # Click analyze single requirement
                for ab in driver.find_elements(By.XPATH, "//button"):
                    atxt = (ab.text or ab.get_attribute("innerText") or "").strip()
                    if "Analyze Single Requirement" in atxt:
                        print(f"[*] Clicking: '{atxt}'")
                        driver.execute_script("arguments[0].click();", ab)
                        time.sleep(6)
                        break
                break

        # Scroll to the refinement section
        driver.execute_script("window.scrollTo(0, 520);")
        time.sleep(2)
        shot_d = TEMP_SHOTS_DIR / "actual_panel_d_single_refinement.png"
        driver.save_screenshot(str(shot_d))
        print(f"[+] Saved Panel D: {shot_d} ({shot_d.stat().st_size:,} bytes)")

        # Assemble Figure 3
        assemble_fig3(shot_a, shot_b, shot_c, shot_d)

    except Exception as e:
        print(f"[-] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()
        proc.terminate()
        print("[*] Server terminated.")


def assemble_fig3(path_a, path_b, path_c, path_d):
    print("[*] Assembling Figure 3 from genuine project screenshots...")

    def crop_window(p, start_y=60, end_y=820):
        im = Image.open(p)
        w, h = im.size
        # Main content area: ignore left sidebar (0 to 325)
        box = (325, start_y, w - 20, min(h, end_y))
        return im.crop(box)

    im_a = crop_window(path_a, 40, 740)
    im_b = crop_window(path_b, 40, 740)
    im_c = crop_window(path_c, 40, 740)
    im_d = crop_window(path_d, 40, 740)

    target_w = 1180
    target_h = 700

    im_a = im_a.resize((target_w, target_h), Image.Resampling.LANCZOS)
    im_b = im_b.resize((target_w, target_h), Image.Resampling.LANCZOS)
    im_c = im_c.resize((target_w, target_h), Image.Resampling.LANCZOS)
    im_d = im_d.resize((target_w, target_h), Image.Resampling.LANCZOS)

    border = 14
    header_h = 36
    cell_w = target_w
    cell_h = target_h + header_h

    comp_w = cell_w * 2 + border * 3
    comp_h = cell_h * 2 + border * 3

    composite = Image.new("RGB", (comp_w, comp_h), "#0F172A")
    draw = ImageDraw.Draw(composite)

    try:
        font = ImageFont.truetype("segoeui.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    panels = [
        (im_a, "(a) Document Overview: Multi-Metric Dashboard (Clean Ratio, Macro ISO, Clarity)", border, border),
        (im_b, "(b) Requirement Explorer: Defect Localization with High-Contrast Span Badges", border * 2 + cell_w, border),
        (im_c, "(c) Grounded Clarification Workspace: Targeted Questions & Stakeholder Answer Capture", border, border * 2 + cell_h),
        (im_d, "(d) Governed Refinement: Side-by-Side Review with Strict Numeric Audit Verdict", border * 2 + cell_w, border * 2 + cell_h),
    ]

    for img, label, x, y in panels:
        # Header bar
        draw.rectangle([x, y, x + cell_w, y + header_h], fill="#1E293B", outline="#334155", width=1)
        draw.text((x + 16, y + 7), label, fill="#F8FAFC", font=font)
        # Screenshot body
        composite.paste(img, (x, y + header_h))
        # Blue outline
        draw.rectangle([x, y, x + cell_w, y + cell_h], outline="#0284C7", width=2)

    out_fig = FIGURES_DIR / "fig3_application_screenshots.png"
    composite.save(str(out_fig), dpi=(300, 300))
    print(f"[SUCCESS] Saved authentic Figure 3: {out_fig} ({out_fig.stat().st_size:,} bytes)")


if __name__ == "__main__":
    run()
