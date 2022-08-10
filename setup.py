from distutils.core import setup
from setuptools import find_packages

setup(
    name='kioblog',
    # packages=['kioblog'],
    packages=find_packages(exclude=('frontendsample', 'kioblogdev', 'media')),
    version='0.1',
    license='MIT',
    description='Simple blog for Django',
    author='Eric Bujeque',
    author_email='noikzyr3@gmail.com',
    url='https://github.com/user/reponame',
    download_url='https://github.com/user/reponame/archive/v_01.tar.gz',
    keywords=['blog', 'django'],
    install_requires=[
        'Django>=3.0',
        'django-robots>=5.0',
        'django-summernote>=0.8.20.0'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',  # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable"
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Blog',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
