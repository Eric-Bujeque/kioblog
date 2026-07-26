from setuptools import find_packages, setup

# No `version=` here on purpose. setuptools_scm derives it from the latest git
# tag at build time (see pyproject.toml), so the tag is the single source of
# truth and there is nothing to keep in sync by hand.
#
# Consequence worth knowing: a build needs the tags present. A shallow clone
# without them produces a 0.1.devN+g<sha> placeholder rather than the real
# version, which is why every workflow that builds checks out with
# fetch-depth: 0.
#
# `download_url` is gone with it - it embedded the version a second time, and
# pointing at a GitHub archive is a pre-PyPI-hosting convention that no
# installer has needed for years.
setup(
    name="kioblog",
    packages=find_packages(exclude=("kioblogdev", "media"), include="./kioblog/templates/*"),
    package_data={"templates": ["kioblog/templates/*"]},
    include_package_data=True,
    license="MIT",
    description="Simple blog for Django",
    author="Eric Bujeque",
    author_email="noikzyr3@gmail.com",
    url="https://github.com/Eric-Bujeque/kioblog",
    keywords=["blog", "django"],
    install_requires=["Django>=3.0", "django-robots>=4.0", "Markdown>=3.3", "Pygments>=2.10", "django-markdownx>=4.0"],
    # 3.8 is the real floor: the package uses f-strings (3.6+) and its
    # dependency floors need more than that. Without this, pip would happily
    # install kioblog on 3.4/3.5 and fail at import with a SyntaxError.
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",  # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable"
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
