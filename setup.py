from distutils.core import setup
from setuptools import find_packages

setup(
    name='kioblog',
    packages=find_packages(exclude=('kioblogdev', 'media'), include="./kioblog/templates/*"),
    package_data={'templates': ['kioblog/templates/*']},
    include_package_data=True,
    version='0.2.1',
    license='MIT',
    description='Simple blog for Django',
    author='Eric Bujeque',
    author_email='noikzyr3@gmail.com',
    url='https://github.com/Eric-Bujeque/kioblog',
    download_url='https://github.com/Eric-Bujeque/kioblog/archive/refs/tags/v0.2.1.tar.gz',
    keywords=['blog', 'django'],
    install_requires=[
        'Django>=3.0',
        'django-robots>=4.0',
        'Markdown>=3.3',
        'Pygments>=2.10',
        'django-markdownx>=4.0'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',  # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable"
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
