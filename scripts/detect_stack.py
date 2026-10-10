#!/usr/bin/env python3
"""
detect_stack.py — scan a repository for manifest/config files and report the
languages, frameworks, and tools it finds. This is a *signal detector*, not a
full dependency parser: it's meant to produce short, distinctive search terms
for skills.sh, not a complete bill of materials.

Usage:
    python3 detect_stack.py [REPO_PATH]

Output: JSON on stdout, shaped like:
{
  "repo": "/path/to/repo",
  "signals": [
    {"term": "spring boot", "kind": "framework", "source": "pom.xml"},
    {"term": "java", "kind": "language", "source": "pom.xml"},
    ...
  ]
}

Each "term" is meant to be used directly as (or folded into) a skills.sh
search query. Dedup is by term; the first file that detects a given term wins
the "source" credit.
"""
import json
import os
import re
import sys
from pathlib import Path

# Directories we never descend into — they're noisy, huge, or not source.
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "target",
    ".venv", "venv", "__pycache__", ".next", ".nuxt", ".turbo",
    "coverage", ".pytest_cache", ".mypy_cache", "out",
}

# How deep to walk looking for manifest files. Most signal lives at repo
# root or one level down (packages/apps in a monorepo), so this stays shallow
# on purpose — this is meant to be fast and cheap, not exhaustive.
MAX_DEPTH = 3

signals = {}  # term -> {"kind": ..., "source": ...}


def add(term, kind, source):
    term = term.strip().lower()
    if not term or term in signals:
        return
    signals[term] = {"term": term, "kind": kind, "source": source}


def read(path, limit=200_000):
    try:
        return path.read_text(errors="ignore")[:limit]
    except OSError:
        return ""


# --- Per-file detectors -----------------------------------------------------
# Each detector gets a Path to an existing file and the relative path string
# used for the "source" field. They should be defensive: these files are
# user data, not trusted input, so no eval/exec, just regex and json.loads
# wrapped in try/except.

def detect_package_json(path, rel):
    add("javascript", "language", rel)
    try:
        data = json.loads(read(path))
    except (json.JSONDecodeError, ValueError):
        return
    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(data.get(key) or {})

    # framework/library signals worth a dedicated skills.sh search
    markers = {
        "next": "Next.js", "react": "React", "react-dom": "React",
        "react-native": "React Native", "expo": "Expo",
        "vue": "Vue", "nuxt": "Nuxt",
        "@angular/core": "Angular",
        "svelte": "Svelte", "@sveltejs/kit": "SvelteKit",
        "express": "Express", "fastify": "Fastify", "koa": "Koa",
        "nestjs": "NestJS", "@nestjs/core": "NestJS",
        "typescript": "TypeScript",
        "tailwindcss": "Tailwind CSS",
        "prisma": "Prisma", "@prisma/client": "Prisma",
        "drizzle-orm": "Drizzle",
        "graphql": "GraphQL", "apollo-server": "Apollo GraphQL",
        "vite": "Vite", "webpack": "Webpack",
        "jest": "Jest", "vitest": "Vitest", "playwright": "Playwright",
        "cypress": "Cypress",
        "electron": "Electron",
        "@trpc/server": "tRPC",
        "redux": "Redux", "zustand": "Zustand",
        "styled-components": "styled-components",
        "@supabase/supabase-js": "Supabase",
        "firebase": "Firebase",
        "mongoose": "MongoDB/Mongoose",
        "stripe": "Stripe",
    }
    for dep, label in markers.items():
        if dep in deps:
            add(label, "framework", rel)

    if "typescript" in deps or Path(path.parent, "tsconfig.json").exists():
        add("typescript", "language", rel)

    engines = data.get("engines") or {}
    if "node" in engines:
        add("node.js", "runtime", rel)


def detect_requirements_txt(path, rel):
    add("python", "language", rel)
    text = read(path)
    markers = {
        "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
        "sqlalchemy": "SQLAlchemy", "pydantic": "Pydantic",
        "celery": "Celery", "pytest": "pytest",
        "numpy": "NumPy", "pandas": "pandas",
        "torch": "PyTorch", "tensorflow": "TensorFlow",
        "transformers": "Hugging Face Transformers",
        "langchain": "LangChain", "openai": "OpenAI SDK",
        "boto3": "AWS (boto3)",
    }
    lowered = text.lower()
    for dep, label in markers.items():
        if re.search(rf"^{re.escape(dep)}\b", lowered, re.MULTILINE):
            add(label, "framework", rel)


def detect_pyproject_toml(path, rel):
    add("python", "language", rel)
    text = read(path).lower()
    if "poetry" in text:
        add("poetry", "tool", rel)
    markers = ["django", "flask", "fastapi", "sqlalchemy", "pydantic", "pytest"]
    for dep in markers:
        if re.search(rf'["\'\s]{re.escape(dep)}\b', text):
            add(dep, "framework", rel)


def detect_pom_xml(path, rel):
    add("java", "language", rel)
    add("maven", "tool", rel)
    text = read(path).lower()
    if "spring-boot" in text or "springframework.boot" in text:
        add("spring boot", "framework", rel)
    elif "springframework" in text:
        add("spring framework", "framework", rel)
    if "junit" in text:
        add("junit", "tool", rel)
    if "hibernate" in text:
        add("hibernate", "framework", rel)


def detect_gradle(path, rel):
    add("java", "language", rel)
    add("gradle", "tool", rel)
    text = read(path).lower()
    if "org.springframework.boot" in text or "spring-boot" in text:
        add("spring boot", "framework", rel)
    if "kotlin" in text:
        add("kotlin", "language", rel)
    if "com.android" in text:
        add("android", "framework", rel)


def detect_go_mod(path, rel):
    add("go", "language", rel)
    text = read(path).lower()
    markers = {
        "gin-gonic/gin": "Gin", "labstack/echo": "Echo",
        "gorilla/mux": "Gorilla Mux", "gofiber/fiber": "Fiber",
        "grpc/grpc-go": "gRPC", "gorm.io/gorm": "GORM",
    }
    for dep, label in markers.items():
        if dep in text:
            add(label, "framework", rel)


def detect_cargo_toml(path, rel):
    add("rust", "language", rel)
    text = read(path).lower()
    markers = {"actix-web": "Actix Web", "axum": "Axum", "tokio": "Tokio", "rocket": "Rocket"}
    for dep, label in markers.items():
        if dep in text:
            add(label, "framework", rel)


def detect_gemfile(path, rel):
    add("ruby", "language", rel)
    text = read(path).lower()
    if "rails" in text:
        add("ruby on rails", "framework", rel)
    if "sinatra" in text:
        add("sinatra", "framework", rel)
    if "rspec" in text:
        add("rspec", "tool", rel)


def detect_composer_json(path, rel):
    add("php", "language", rel)
    text = read(path).lower()
    if "laravel" in text:
        add("laravel", "framework", rel)
    if "symfony" in text:
        add("symfony", "framework", rel)


def detect_csproj(path, rel):
    add("c#", "language", rel)
    add(".net", "framework", rel)
    text = read(path).lower()
    if "microsoft.aspnetcore" in text:
        add("asp.net core", "framework", rel)


def detect_dockerfile(path, rel):
    add("docker", "tool", rel)
    text = read(path).lower()
    m = re.search(r"^from\s+([a-z0-9][a-z0-9._/-]*)", text, re.MULTILINE)
    if m:
        base = m.group(1)
        for lang in ("node", "python", "golang", "ruby", "openjdk", "rust", "php"):
            if lang in base:
                add({"node": "node.js", "golang": "go", "openjdk": "java"}.get(lang, lang),
                    "language", rel)


def detect_compose(path, rel):
    add("docker compose", "tool", rel)
    text = read(path).lower()
    for svc in ("postgres", "mysql", "redis", "mongo", "rabbitmq", "kafka", "elasticsearch"):
        if svc in text:
            add(svc, "infra", rel)


def detect_terraform(path, rel):
    add("terraform", "tool", rel)
    text = read(path).lower()
    for provider in ("aws", "google", "azurerm", "kubernetes"):
        if f'provider "{provider}"' in text:
            add({"azurerm": "azure", "google": "gcp"}.get(provider, provider), "infra", rel)


def detect_k8s(path, rel):
    text = read(path)
    if re.search(r"^kind:\s*(Deployment|Service|Ingress|StatefulSet)", text, re.MULTILINE):
        add("kubernetes", "infra", rel)


def detect_github_workflow(path, rel):
    add("github actions", "tool", rel)


FILE_DETECTORS = {
    "package.json": detect_package_json,
    "requirements.txt": detect_requirements_txt,
    "pyproject.toml": detect_pyproject_toml,
    "pom.xml": detect_pom_xml,
    "go.mod": detect_go_mod,
    "cargo.toml": detect_cargo_toml,
    "gemfile": detect_gemfile,
    "composer.json": detect_composer_json,
    "dockerfile": detect_dockerfile,
    "docker-compose.yml": detect_compose,
    "docker-compose.yaml": detect_compose,
}

SUFFIX_DETECTORS = {
    ".csproj": detect_csproj,
    ".tf": detect_terraform,
}

GRADLE_NAMES = {"build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"}


def walk(root: Path):
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        depth = len(rel_dir.parts)
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and (not d.startswith(".") or d == ".github")
        ]
        if depth >= MAX_DEPTH:
            dirnames[:] = []

        for name in filenames:
            path = Path(dirpath, name)
            rel = str(Path(rel_dir, name)) if str(rel_dir) != "." else name
            lower = name.lower()

            if lower in FILE_DETECTORS:
                FILE_DETECTORS[lower](path, rel)
            elif lower in GRADLE_NAMES:
                detect_gradle(path, rel)
            elif lower.endswith(tuple(SUFFIX_DETECTORS)):
                for suffix, fn in SUFFIX_DETECTORS.items():
                    if lower.endswith(suffix):
                        fn(path, rel)
            elif lower.endswith((".yml", ".yaml")):
                if "workflows" in rel_dir.parts:
                    detect_github_workflow(path, rel)
                elif depth <= 1:
                    detect_k8s(path, rel)


def main():
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    if not repo.exists():
        print(json.dumps({"error": f"path not found: {repo}"}))
        sys.exit(1)

    walk(repo)

    result = {
        "repo": str(repo.resolve()),
        "signals": sorted(signals.values(), key=lambda s: (s["kind"], s["term"])),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
