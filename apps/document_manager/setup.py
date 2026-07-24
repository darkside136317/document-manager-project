from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = [
        line.strip() for line in f.read().strip().split("\n")
        if line.strip() and not line.startswith("#") and not line.startswith("frappe")
    ]

setup(
    name="document_manager",
    version="0.1.0",
    description="Hệ thống Quản lý & Khai thác Hồ sơ Lưu trữ Số hóa",
    author="Document Manager Team",
    author_email="admin@docmanager.local",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
