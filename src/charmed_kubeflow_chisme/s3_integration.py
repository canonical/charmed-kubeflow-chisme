# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import dataclasses
import json
import logging
import os
import shutil
import socket
import subprocess
from pathlib import Path

from juju.model import Model
from tenacity import retry, stop_after_attempt, wait_fixed

from charmed_kubeflow_chisme.testing import CharmSpec


@dataclasses.dataclass(frozen=True)
class S3ConnectionInfo:
    endpoint: str
    access_key: str
    secret_key: str
    region: str
    tls_ca_chain: str


SECRET_LABEL = "s3-secret"

logger = logging.getLogger(__name__)

_DEFAULT_S3_INTEGRATOR = CharmSpec(
    charm="s3-integrator",
    channel="2/edge",
    trust=False,
)


def host_ip() -> str:
    """The IP address of the host running these tests."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("1.1.1.1", 80))
        return s.getsockname()[0]


def local_tmp_folder(name: str = "tmp") -> Path:
    tmp_folder = Path.cwd() / name
    if tmp_folder.exists():
        shutil.rmtree(tmp_folder)
    tmp_folder.mkdir()
    return tmp_folder


def certs_path() -> Path:
    """A temporary directory to store certificates and keys."""
    return local_tmp_folder("temp-certs")


@retry(stop=stop_after_attempt(20), wait=wait_fixed(3), reraise=True)
def wait_for_rgw_ready():
    """Wait for RADOS Gateway to be ready by checking if account list command succeeds."""
    subprocess.run(
        ["sudo", "microceph.radosgw-admin", "account", "list"],
        capture_output=True,
        check=True,
        encoding="utf-8",
    )


def install_microceph():
    """Install and bootstrap microceph if not already installed."""
    if subprocess.run(["snap", "list", "microceph"], capture_output=True).returncode == 0:
        logger.info("microceph already installed, skipping install and bootstrap")
        return

    logger.info("Installing microceph")
    subprocess.run(["sudo", "snap", "install", "microceph"], check=True)
    try:
        subprocess.run(
            ["sudo", "microceph", "cluster", "bootstrap"],
            check=True,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as ex:
        logger.error(ex.stderr.decode())
    subprocess.run(["sudo", "microceph", "disk", "add", "loop,1G,3"], check=True)


def setup_radosgw(host_ip: str, certs_path: Path):
    """Generate TLS certificates and enable the RADOS Gateway."""
    logger.info("Generating TLS certificates")
    subprocess.run(["openssl", "genrsa", "-out", str(certs_path / "ca.key"), "2048"], check=True)
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-new",
            "-nodes",
            "-key",
            str(certs_path / "ca.key"),
            "-days",
            "1024",
            "-out",
            str(certs_path / "ca.crt"),
            "-outform",
            "PEM",
            "-subj",
            f"/C=US/ST=Denial/L=Springfield/O=Dis/CN={host_ip}",
        ],
        check=True,
    )
    subprocess.run(
        ["openssl", "genrsa", "-out", str(certs_path / "server.key"), "2048"],
        check=True,
    )
    subprocess.run(
        [
            "openssl",
            "req",
            "-new",
            "-key",
            str(certs_path / "server.key"),
            "-out",
            str(certs_path / "server.csr"),
            "-subj",
            f"/C=US/ST=Denial/L=Springfield/O=Dis/CN={host_ip}",
        ],
        check=True,
    )
    with open(certs_path / "extfile.cnf", "w") as extfile:
        extfile.write(f"subjectAltName = DNS:{host_ip}, IP:{host_ip}")
    subprocess.run(
        [
            "openssl",
            "x509",
            "-req",
            "-in",
            str(certs_path / "server.csr"),
            "-CA",
            str(certs_path / "ca.crt"),
            "-CAkey",
            str(certs_path / "ca.key"),
            "-CAcreateserial",
            "-out",
            str(certs_path / "server.crt"),
            "-days",
            "365",
            "-extfile",
            str(certs_path / "extfile.cnf"),
        ],
        check=True,
    )

    server_crt_base64 = subprocess.run(
        ["sudo", "base64", "-w0", str(certs_path / "server.crt")],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    server_key_base64 = subprocess.run(
        ["sudo", "base64", "-w0", str(certs_path / "server.key")],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()

    logger.info("Enabling RADOS Gateway")
    try:
        subprocess.run(
            [
                "sudo",
                "microceph",
                "enable",
                "rgw",
                "--ssl-certificate",
                server_crt_base64,
                "--ssl-private-key",
                server_key_base64,
            ],
            check=True,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as ex:
        logger.warning(
            "microceph enable rgw failed (may already be enabled): %s", ex.stderr.decode()
        )

    wait_for_rgw_ready()


def create_root_user(host_ip: str, certs_path: Path) -> "S3ConnectionInfo":
    """Create the root account and IAM user, reusing existing credentials if present."""
    result = subprocess.run(
        ["sudo", "microceph.radosgw-admin", "user", "info", "--uid", "root-iam-user"],
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode == 0:
        logger.info("Root IAM user already exists, reusing credentials")
        key = json.loads(result.stdout)["keys"][0]
    else:
        logger.info("Creating user account...")
        output = subprocess.run(
            [
                "sudo",
                "microceph.radosgw-admin",
                "account",
                "create",
                "--account-name",
                "root-account",
                "--email",
                "test@example.com",
            ],
            capture_output=True,
            check=True,
            encoding="utf-8",
        ).stdout
        root_account_id = json.loads(output)["id"]

        logger.info("Creating root IAM user...")
        output = subprocess.run(
            [
                "sudo",
                "microceph.radosgw-admin",
                "user",
                "create",
                "--uid",
                "root-iam-user",
                "--display-name",
                "root-iam-user",
                "--account-id",
                root_account_id,
                "--account-root",
                "--gen-secret",
                "--gen-access-key",
            ],
            capture_output=True,
            check=True,
            encoding="utf-8",
        ).stdout
        key = json.loads(output)["keys"][0]

    ca_crt_base64 = subprocess.run(
        ["sudo", "base64", "-w0", str(certs_path / "ca.crt")],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()

    return S3ConnectionInfo(
        endpoint=f"https://{host_ip}",
        access_key=key["access_key"],
        secret_key=key["secret_key"],
        tls_ca_chain=ca_crt_base64,
        region="default",
    )


def setup_microceph() -> "S3ConnectionInfo":
    """Set up microceph, radosgw, account, and root user; return S3 connection info.

    If S3_ACCESS_KEY, S3_SECRET_KEY, and S3_ENDPOINT environment variables are
    set, the microceph setup is skipped entirely and credentials are taken from
    the environment. S3_TLS_CA may optionally be set to supply a base64-encoded
    CA certificate.
    """
    logger.info(os.environ.get("S3_ACCESS_KEY"))
    if (
        os.environ.get("S3_ACCESS_KEY")
        and os.environ.get("S3_SECRET_KEY")
        and os.environ.get("S3_ENDPOINT")
    ):
        logger.info("S3 credentials found in environment, skipping microceph setup")
        return S3ConnectionInfo(
            endpoint=os.environ["S3_ENDPOINT"],
            access_key=os.environ["S3_ACCESS_KEY"],
            secret_key=os.environ["S3_SECRET_KEY"],
            tls_ca_chain=os.environ.get("S3_TLS_CA", ""),
            region=os.environ.get("S3_REGION", "default"),
        )
    ip = host_ip()
    path = certs_path()
    install_microceph()
    setup_radosgw(ip, path)
    return create_root_user(ip, path)


async def deploy_and_assert_s3_integrator(
    model: Model,
    add_ca_chain: bool = False,
    s3_integrator: CharmSpec = _DEFAULT_S3_INTEGRATOR,
):
    """Deploy the s3-integrator charm with configured credentials."""
    s3_connection_info = setup_microceph()
    config = {"endpoint": s3_connection_info.endpoint}
    if add_ca_chain and s3_connection_info.tls_ca_chain:
        config["tls-ca-chain"] = s3_connection_info.tls_ca_chain

    logger.info("Deploying s3-integrator charm with configured credentials...")
    await model.deploy(
        s3_integrator.charm,
        config=config,
        channel=s3_integrator.channel,
        trust=s3_integrator.trust,
    )
    secret_uri = await model.add_secret(
        name=SECRET_LABEL,
        data_args=[
            f"access-key={s3_connection_info.access_key}",
            f"secret-key={s3_connection_info.secret_key}",
        ],
    )
    await model.grant_secret(SECRET_LABEL, s3_integrator.charm)
    app = model.applications.get(s3_integrator.charm)
    await app.set_config({"credentials": secret_uri})
    await model.wait_for_idle(apps=[s3_integrator.charm], status="active", timeout=60 * 10)
