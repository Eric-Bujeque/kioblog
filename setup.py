from setuptools import setup, find_packages

setup(
    name='kioblog',
    packages=find_packages(exclude=['kioblogdev', 'kioblogdev.*', 'media']),
    package_data={
        'kioblog': [
            'templates/kioblog/*.html',
            'templates/kioblog/includes/*.html',
            'static/kioblog/css/*.css',
            'migrations/*.py',
        ],
    },
    include_package_data=True,
    version='0.1.4a0',
    license='MIT',
    description='Simple blog for Django',
    author='Eric Bujeque',
    author_email='noikzyr3@gmail.com',
    url='https://github.com/Eric-Bujeque/kioblog',
    download_url='https://github.com/Eric-Bujeque/kioblog/archive/refs/tags/v0.1.4-alpha.tar.gz',
    keywords=['blog', 'django'],
    python_requires='>=3.8',
    install_requires=[
        'Django>=5.1',
        'django-robots>=6.1',
        'django-summernote>=0.8.20.0',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)
