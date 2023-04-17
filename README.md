# WikiBase Data Connector
This repository contains a Python library that provides a connector to the WikiBase database. WikiBase is a free and open knowledge base that can be read and edited by both humans and machines, and that contains structured data and metadata about a wide range of topics.

### Installation
To install the library, you can use pip:

```sh
pip install wikibasedataconnector
```
### Usage
To use the library, you need to create an instance of the WikiBaseDataConnector class, and then call its methods to process data into the WikiBase. For example:

```python
import json
import csv
import asyncio
from wikibasedataconnector import WBDC

conf_filepath = 'conf'
site_name = <SITE>
PATH = f'{conf_filepath}/import_properties_add.json'
with open(PATH, 'r', encoding='utf-8') as f:
        mapping_config = json.load(f)

bot = WBDC(site_name)
bot.set_mapping_config(mapping_config)

FILEPATH = 'data/properties.csv'
with open(FILEPATH, 'r', encoding='utf-8') as file:
    csv_file = csv.reader(file)
    next(csv_file)
    await asyncio.gather(*[bot.process(row) for row in csv_file])
```
This code will read and process the `properties.csv` file according to the `import_properties_add.json` configuration file. 
More examples can be found in `example/example_upsert.ipynb`.

This uses the Pywikibot library, so it is required to create a family file and generated user files if you're using a custom wikibase.

### To create family and user files

* create `<family-filename>` family using command `pwb generate_family_file`
    - set url and a desired name for family
    - add the following code to your familyfile i.e. `<family-filename>_family.py`
    ```
        def default_globe(self, code) -> str:
        """Default globe for Coordinate datatype."""
        return 'earth'

    def globes(self, code):
        """Supported globes for Coordinate datatype."""
        return {
            'earth': 'http://www.wikidata.org/entity/Q2'
        }
    ```

* ensuring that you are in the same directory as where you generated the family file, create user config and password files with command `pwb generate_user_files`
    - selected yes on adding a BotPassword
    - used same name for bot when it was created within the wikibase instance
    - add password provided by wikibase instance
    - It will prompt on whether to add additional options in the user-config.py file. They're not necessary to set up for the connection to the wikibase to be established.

* change user-config file to read only by running `chmod 0444 user-config.py`
    (`Set-ItemProperty -Path ./user-config.py -Name IsReadOnly -Value $true` for Windows)

* run `pwb login` to test connection

### Troubleshooting

It is possible that the path was not added to the environment. If that is the case, a warning such as this will pop up:
    ```
        WARNING: The script pwb.exe is installed in 'your/path/to/local-packages/Python310/Scripts' which is not on PATH.
        Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
    ```

You can add the path by running `export PATH=$PATH:/some/new/path` 

Note: If you are on Windows, instructions to add the path can be found [here](https://learn.microsoft.com/en-us/previous-versions/office/developer/sharepoint-2010/ee537574(v=office.14))

    you can test to see if pywikibot is working by running the command `pwb`

### License

This library is released under the MIT License. Please refer to the LICENSE file for more information.
