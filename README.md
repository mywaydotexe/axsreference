# axsreference

A post-consumption script for [Paperless-NGX](https://github.com/paperless-ngx/paperless-ngx) that automatically reads barcodes from scanned documents and updates custom fields in Paperless-NGX via its REST API.

---

## What it does

When Paperless-NGX finishes consuming a document, this script is triggered automatically. It then:

1. **Scans the document** (image or PDF) for barcodes using `pyzbar`
2. **Parses barcodes** matching the pattern `ORGANISATION-LOCATION-NUMBER` (e.g. `ACM-WH1-00042`)
3. **Looks up** the organisation and location names from a configuration file
4. **Updates the document** in Paperless-NGX with the following custom fields:
   - Organisation (select field)
   - Location (select field)
   - Reference number (number field)
   - Additional barcodes found on the document (text field)

---

## Requirements

- Python 3.8+
- A running [Paperless-NGX](https://github.com/paperless-ngx/paperless-ngx) instance



## Configuration
Copy axsreference.ini.example to axsreference.ini and fill in your values:

```
[axsreference]
apitoken          = YOUR_PAPERLESS_API_TOKEN
paperlessurl      = http://your-paperless-instance:8000
barcodeidentify   = true
barcodefield      = Barcode
organisationfield = Organisation
locationfield     = Location
numberfield       = Reference Number

[organisations]
ACM = ACME Corporation
EXA = Example Organisation
SOC = Soccer Club
FAM = Family


[locations]
WH1 = Warehouse 1
HO1 = Home Office Mike
HO2 = Home Office Adam
A = Binder
X = Shredder

```

## Field descriptions
[axsreference]

| Key	| Description |
| --- | --- |
| apitoken | 	Paperless-NGX API token |
| paperlessurl | Base URL of your Paperless-NGX instance |
| barcodeidentify |	If true, additional (non-reference) barcodes are also saved |
| barcodefield | Name of the custom text field for additional barcodes |
| organisationfield | Name of the custom select field for the organisation |
| locationfield | Name of the custom select field for the location |
| numberfield	| Name of the custom number field for the reference number |

[organisations]

| Key	| Description |
| --- | --- |
| CODE | Full Name of the select Option  of custom field {organisationfield} |

Maps short barcode codes to full organisation names.
Each entry follows the format CODE = Full Name.

The CODE is the uppercase identifier used in the barcode (e.g. ACM in ACM-WH1-00042).
The Full Name must exactly match the label of the corresponding select option in your paperless custom field {organisationfield configured in [axsreference]}.

[locations]

| Key	| Description |
| --- | --- |
| CODE | Full Name of the select Option  of custom field {locationfield} |

Maps short barcode codes to full location names.
Each entry follows the format CODE = Full Name.

The CODE is the uppercase identifier used in the barcode (e.g. WH1 in ACM-WH1-00042).
The Full Name must exactly match the label of the corresponding select option in your paperless custom field {locationfield configured in [axsreference]}

## Installation
Installation as a Paperless-NGX post-consumption script

For any potential extensions, you should place a wrapper in front of the axsreference — if you don't already have one.

Place the post-consumption-wrapper.sh in a directory accessible by your Paperless-NGX instance.  
e.g. {paperless dir}/scripts

Place axsreference.py and axsreference.ini in a directory accessible by your Paperless-NGX instance.  
e.g. {paperless dir}/scrips/axsreference

Set the post-consumption script path in your Paperless-NGX configuration (paperless.conf or environment variable):  
PAPERLESS_POST_CONSUME_SCRIPT={paperless dir}/scripts/post-consumption-wrapper.sh

Restart Paperless-NGX.
Paperless-NGX will now automatically call the script after every consumed document, passing DOCUMENT_ID and DOCUMENT_PATH as environment variables.

## Barcode format
The script recognises barcodes in the following format:

ORGANISATION-LOCATION-NUMBER  
ORGANISATION — uppercase letters, must match a key in the [organisations] config section  
LOCATION — uppercase letters, must match a key in the [locations] config section  
NUMBER — one or more digits  
Example: ACM-WH1-00042  

## TODO

Intergrate document split   
Adding autoincrementing reference e.g. ACM-WH1-INC  
Adding a simple version management, when the same reference is registered more than once    
Adding text location e.g. ACM-WH2-redshelf for locationgroup 

## License
MIT
