"""
USB Automation Tool - Upload to GitHub via API (không cần Git CLI)

Cách dùng:
  1. Tạo Personal Access Token trên GitHub:
     - Vào https://github.com/settings/tokens
     - Click "Generate new token (classic)"
     - Tick: repo (full control)
     - Copy token
  2. Chạy: python upload_to_github.py
"""

import os
import base64
import json
import time
from pathlib import Path
import urllib.request
import urllib.error

PROJECT_DIR = Path(__file__).parent

SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv"}
SKIP_FILES = {".env", "screenshot_tmp.png", "recording_tmp.mp4"}
SKIP_EXTENSIONS = {".pyc", ".pyo", ".db", ".log"}
MAX_FILE_SIZE = 100 * 1024 * 1024


def get_all_files():
    files = []
    for root, dirs, filenames in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in filenames:
            filepath = os.path.join(root, filename)
            relpath = os.path.relpath(filepath, PROJECT_DIR).replace("\\", "/")
            if filename in SKIP_FILES:
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext in SKIP_EXTENSIONS:
                continue
            if os.path.getsize(filepath) > MAX_FILE_SIZE:
                print(f"  ⚠️ Bỏ qua file lớn: {relpath}")
                continue
            files.append((filepath, relpath))
    return files


def github_api(method, endpoint, token, data=None, retries=3):
    url = f"https://api.github.com{endpoint}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "USB-Auto-Tool-Uploader",
    }
    body = json.dumps(data).encode("utf-8") if data else None

    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 204:
                    return None
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if e.code == 422 and "already exists" in error_body:
                return None
            if e.code == 404:
                raise Exception(f"Not Found (404): {endpoint} - Kiểm tra repo name và token quyền repo")
            raise Exception(f"GitHub API error {e.code}: {error_body[:300]}")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep((attempt + 1) * 3)
            else:
                raise Exception(f"Connection error: {e}")


def create_repo(username, token, repo_name, private=True):
    """Tạo repository mới trên GitHub."""
    # Kiểm tra repo đã tồn tại chưa
    try:
        result = github_api("GET", f"/repos/{username}/{repo_name}", token)
        if result and result.get("html_url"):
            print(f"✅ Repository đã tồn tại: {result['html_url']}")
            return result["html_url"]
    except Exception:
        pass

    # Tạo repo mới
    print(f"📦 Đang tạo repository '{repo_name}'...")
    try:
        result = github_api("POST", "/user/repos", token, {
            "name": repo_name,
            "private": private,
            "description": "USB Automation Tool - Điều khiển nhiều thiết bị Android qua USB",
            "auto_init": False,
        })
        if result and result.get("html_url"):
            print(f"✅ Đã tạo repository: {result['html_url']}")
            return result["html_url"]
    except Exception as e:
        if "already exists" in str(e).lower() or "422" in str(e):
            url = f"https://github.com/{username}/{repo_name}"
            print(f"✅ Repository đã tồn tại: {url}")
            return url
        raise

    url = f"https://github.com/{username}/{repo_name}"
    print(f"✅ Repository sẵn sàng: {url}")
    return url


def get_file_sha(username, token, repo_name, relpath, branch="main"):
    try:
        result = github_api("GET", f"/repos/{username}/{repo_name}/contents/{relpath}?ref={branch}", token)
        if result and result.get("sha"):
            return result["sha"]
    except Exception:
        pass
    return None


def upload_file(username, token, repo_name, filepath, relpath, branch="main"):
    with open(filepath, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    existing_sha = get_file_sha(username, token, repo_name, relpath, branch)

    data = {
        "message": f"Update {relpath}" if existing_sha else f"Add {relpath}",
        "content": content,
        "branch": branch,
    }

    if existing_sha:
        data["sha"] = existing_sha

    try:
        github_api("PUT", f"/repos/{username}/{repo_name}/contents/{relpath}", token, data)
        return True
    except Exception as e:
        print(f"\n  ❌ Lỗi upload {relpath}: {e}")
        return False


def main():
    print("=" * 60)
    print("🚀 USB Automation Tool — Upload to GitHub")
    print("=" * 60)
    print()
    print("📌 Cần Personal Access Token với quyền 'repo'")
    print("   Tạo tại: https://github.com/settings/tokens")
    print()

    username = input("👤 GitHub username: ").strip()
    token = input("🔑 Personal Access Token: ").strip()
    repo_name = input("📁 Repository name [usb-automation-tool]: ").strip() or "usb-automation-tool"
    private_input = input("🔒 Private repo? (Y/n): ").strip().lower()
    private = private_input != "n"

    if not username or not token:
        print("❌ Cần nhập username và token!")
        return

    print()

    # Step 1: Create repository
    try:
        repo_url = create_repo(username, token, repo_name, private)
    except Exception as e:
        print(f"❌ Lỗi tạo repository: {e}")
        print("💡 Kiểm tra token có quyền 'repo' không?")
        return

    # Step 2: Get all files
    print()
    print("📂 Đang quét file...")
    files = get_all_files()
    print(f"📋 Tìm thấy {len(files)} file cần upload")
    print()

    # Step 3: Upload files
    success = 0
    failed = 0

    for i, (filepath, relpath) in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] Uploading: {relpath}...", end=" ", flush=True)
        try:
            if upload_file(username, token, repo_name, filepath, relpath):
                success += 1
                print("✅")
            else:
                failed += 1
                print("❌")
        except Exception as e:
            failed += 1
            print(f"❌ {e}")

        # Rate limiting
        if i % 40 == 0:
            print("  ⏳ Nghỉ 2s tránh rate limit...")
            time.sleep(2)

    # Done
    print()
    print("=" * 60)
    print(f"✅ Upload hoàn tất!")
    print(f"   Thành công: {success}/{len(files)}")
    if failed:
        print(f"   Thất bại: {failed}/{len(files)}")
    print()
    print(f"🔗 Repository: https://github.com/{username}/{repo_name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
