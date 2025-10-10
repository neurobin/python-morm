#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS_FILE="$ROOT_DIR/requirements.txt"
VENV_DIR="${1:-$ROOT_DIR/.venv_test}"

POSTGRES_USER=jahid
POSTGRES_PASS='md5709c4fb68f87bdae8d9698d2f3368dc6'
POSTGRES_DB=test

print(){
    echo
    echo "==== $* ===="
}

command_exists(){
    command -v "$1" >/dev/null 2>&1
}

# Return distro id like Ubuntu, Debian, Manjaro, Arch, etc.
detect_distro(){
    if command_exists lsb_release; then
        lsb_release -si
        return
    fi
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        # Prefer ID_LIKE if available to catch derivatives
        if [ -n "${ID_LIKE-}" ]; then
            echo "$ID_LIKE"
        else
            echo "$ID"
        fi
        return
    fi
    echo "unknown"
}

ensure_postgresql(){
    if command_exists psql; then
        print "PostgreSQL already installed"
        return
    fi

    DISTRO=$(detect_distro | tr '[:upper:]' '[:lower:]')
    print "PostgreSQL not found. Detected distro: $DISTRO. Attempting to install..."

    if echo "$DISTRO" | grep -q "ubuntu\|debian\|linuxmint" && command_exists apt-get; then
        sudo apt-get update
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql postgresql-contrib
        print "Installed PostgreSQL via apt-get"
        return
    fi

    if echo "$DISTRO" | grep -q "manjaro\|arch" && command_exists pacman; then
        # Arch/Manjaro
        print "Installing PostgreSQL via pacman (Arch/Manjaro)..."
        sudo pacman -Sy --noconfirm postgresql || true
        # Initialize database cluster if not initialized
        if [ ! -d /var/lib/postgres/data ]; then
            print "Initializing PostgreSQL database cluster for Arch/Manjaro"
            sudo -u postgres bash -c 'initdb --locale "$LANG" -D /var/lib/postgres/data' || true
        fi
        print "Installed PostgreSQL via pacman"
        return
    fi

    # Fallbacks for other package managers
    if command_exists yum; then
        sudo yum install -y postgresql-server postgresql-contrib || true
        print "Attempted install via yum"
        return
    fi
    if command_exists dnf; then
        sudo dnf install -y postgresql-server postgresql-contrib || true
        print "Attempted install via dnf"
        return
    fi

    print "Could not find a supported package manager to install PostgreSQL automatically. Please install it manually and re-run this script."
    exit 1
}

ensure_postgres_running(){
    # Try to start postgres service if it's installed but not running
    if ! pg_isready -q; then
        print "PostgreSQL not accepting connections. Attempting to start service..."
        # On Arch/Manjaro the service is postgresql, on Debian/Ubuntu it's postgresql
        if command_exists systemctl; then
            # prefer postgresql.service, but try both common names
            sudo systemctl enable --now postgresql.service || sudo systemctl enable --now postgresql || true
        else
            sudo service postgresql start || true
        fi
        # wait a little for postgres to come up
        for i in {1..10}; do
            if pg_isready -q; then
                print "PostgreSQL is ready"
                return
            fi
            sleep 1
        done
        print "PostgreSQL did not start in time"
        exit 1
    else
        print "PostgreSQL is accepting connections"
    fi
}

create_role_and_db(){
    print "Creating role '$POSTGRES_USER' (if not exists) and database '$POSTGRES_DB' (if not exists)"

    # Create role if not exists
    sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER}'" | grep -q 1 || \
        sudo -u postgres psql -c "CREATE ROLE ${POSTGRES_USER} WITH LOGIN NOSUPERUSER INHERIT CREATEDB NOCREATEROLE REPLICATION ENCRYPTED PASSWORD '${POSTGRES_PASS}';"

    # Create database if not exists
    sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" | grep -q 1 || \
        sudo -u postgres psql -c "CREATE DATABASE ${POSTGRES_DB} WITH OWNER = ${POSTGRES_USER} ENCODING = 'UTF8' CONNECTION LIMIT = -1;"

    print "Role and database creation complete (or they already existed)."
}

create_venv_and_install(){
    print "Setting up Python virtual environment at ${VENV_DIR}"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi

    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip

    if [ -f "$REQUIREMENTS_FILE" ]; then
        pip install -r "$REQUIREMENTS_FILE"
    else
        print "No requirements.txt found at $REQUIREMENTS_FILE. Installing minimal deps: coverage,mypy"
        pip install coverage mypy pdoc3
    fi

    # Ensure required tooling is available in the venv
    print "Ensuring coverage, pdoc3, mypy are installed in the virtualenv"
    pip install --upgrade coverage pdoc3 mypy || true

    # Ensure run_tests.sh is executable
    chmod +x "$ROOT_DIR/run_tests.sh"
}

run_tests(){
    print "Running test suite via ./run_tests.sh"
    # We already activated venv in create_venv_and_install
    (cd "$ROOT_DIR" && ./run_tests.sh)
}

main(){
    print "Starting local test environment setup"

    ensure_postgresql
    ensure_postgres_running
    create_role_and_db
    create_venv_and_install
    # run_tests

    print "All done"
}

main "$@"
