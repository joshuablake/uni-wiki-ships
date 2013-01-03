from distribute_setup import use_setuptools
use_setuptools()
from setuptools import setup

setup(
      name='Uni Wiki Ships',
      version='0.1.0',
      packages=['uni_wiki_ships'],
      entry_points={
        'console_scripts': [
            'wikiships = uni_wiki_ships.main:main',
        ]
      },
      
      author="Joshua Blake",
      author_email="joshbblake@gmail.com",
      description="This package works out problems with E-Uni's Ship Database",
      license="BSD",
      keywords="hello world example examples",
      url="https://github.com/joshuablake/uni-wiki-ships",
      long_description=open('README.rst').read(),
)
