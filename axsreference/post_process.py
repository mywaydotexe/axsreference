import os
import re
import logging
import requests
import configparser
from pathlib import Path
from pyzbar.pyzbar import decode
from PIL import Image
from functools import lru_cache

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None


# -----------------------------------------
# CONFIGURATION
# -----------------------------------------

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("axsreference")

script_dir = Path(__file__).parent
config_path = script_dir / "axsreference.ini"

config = configparser.ConfigParser()
config.optionxform = str  # preserve uppercase keys
read_files = config.read(config_path)
log.debug(f"Loaded config: {read_files}")

data = {
    "axsreference": {
        "apitoken":          config.get("axsreference", "apitoken"),
        "paperlessurl":      config.get("axsreference", "paperlessurl"),
        "barcodeidentify":   config.getboolean("axsreference", "barcodeidentify"),
        "barcodefield":        config.get("axsreference", "barcodefield"),
        "organisationfield": config.get("axsreference", "organisationfield"),
        "locationfield":     config.get("axsreference", "locationfield"),
        "numberfield":       config.get("axsreference", "numberfield"),
    },
    "organisations": dict(config.items("organisations")),
    "locations":     dict(config.items("locations")),
}

log.debug(f"organisations: {data['organisations']}")
log.debug(f"locations:     {data['locations']}")


# -----------------------------------------
# MATCH ORGANISATIONS AND LOCATIONS
# -----------------------------------------

def get_storage_location(s, organisations, locations):
    """
    Parses a reference string of the form ORG-LOC-NUMBER.
    Returns a dict with resolved names, or None if no match.
    """
    pattern = r"^([A-Z]+)-([A-Z]+)-(\d+)$"
    match = re.match(pattern, s)

    if not match:
        return None

    org_code, loc_code, number = match.groups()
    log.info(f"Regex matched ? organisation={org_code}, location={loc_code}")

    if org_code not in organisations or loc_code not in locations:
        log.error(f"Unknown organisation '{org_code}' or location '{loc_code}' in configuration.")
        return None

    return {
        "organisation_code": org_code,
        "organisation_name": organisations[org_code],
        "location_code":     loc_code,
        "location_name":     locations[loc_code],
        "number":            number,
    }


# -----------------------------------------
# BARCODE DECODING
# -----------------------------------------

def decode_image(img):
    """Decodes all barcodes from a PIL image and returns a list of strings."""
    results = []
    for code in decode(img):
        try:
            results.append(code.data.decode("utf-8"))
        except Exception:
            pass
    return results


# -----------------------------------------
# SCAN FILE FOR BARCODES
# -----------------------------------------

def scan_file(path):
    """
    Scans an image or PDF file for barcodes.
    Returns a list of decoded barcode strings.
    """
    barcodes = []

    if path.lower().endswith(".pdf"):
        if convert_from_path is None:
            log.error("pdf2image is not installed.")
            return []
        for page in convert_from_path(path, dpi=300):
            barcodes.extend(decode_image(page))
    else:
        barcodes.extend(decode_image(Image.open(path)))

    return barcodes


# -----------------------------------------
# PAPERLESS API HELPERS
# -----------------------------------------

def get_custom_field_mapping(paperless_url, api_token):
    """
    Fetches custom fields from Paperless and returns a mapping dict:
    {
        "FieldName": {
            "field_id": int,
            "data_type": str,
            "options": {"Label": "option-id", ...}  # select fields only
        },
        ...
    }
    """

    url     = f"{paperless_url}/api/custom_fields/"
    headers = {"Authorization": f"Token {api_token}"}
    mapping = {}


    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        response_data = response.json()
    except requests.exceptions.RequestException as e:
        log.error(f"Failed to fetch custom fields: {e}")
        raise

    if isinstance(response_data, dict) and "results" in response_data:
        fields = response_data["results"]
    elif isinstance(response_data, list):
        fields = response_data
    else:
        log.error(f"Unrecognised API response: {response_data}")
        return {}

    for field in fields:
        field_name = field.get("name")
        if not field_name:
            continue

        entry = {
            "field_id":  field.get("id"),
            "data_type": field.get("data_type"),
        }

        if entry["data_type"] == "select":
            select_options = field.get("extra_data", {}).get("select_options", [])
            entry["options"] = {opt["label"]: opt["id"] for opt in select_options}

        mapping[field_name] = entry

    return mapping


def _build_select_field(mapping, field_name, label):
    """
    Validates and builds a custom_fields entry for a select field.
    Returns the entry dict, or raises ValueError on misconfiguration.
    """
    entry = mapping[field_name]
    if entry["data_type"] != "select":
        raise ValueError(f"Field '{field_name}' is not a select field.")
    if label not in entry["options"]:
        raise ValueError(f"Label '{label}' not found in options of '{field_name}'.")
    return {"field": entry["field_id"], "value": entry["options"][label]}


def update_document(doc_id, organisation_label, location_label, number_value, bcd_value):
    """
    Updates the custom fields of a Paperless document.

    Args:
        doc_id:             Paperless document ID.
        organisation_label: Select option label for the organisation field.
        location_label:     Select option label for the location field.
        number_value:       Value for the number (integer/text) field.
        bcd_value:          Value for the barcode (string) field.
    """
    mapping = get_custom_field_mapping(
        data["axsreference"]["paperlessurl"],
        data["axsreference"]["apitoken"],
    )

    if not mapping:
        log.error("No custom fields returned � aborting update.")
        return

    org_field_name = data["axsreference"]["organisationfield"]
    loc_field_name = data["axsreference"]["locationfield"]
    num_field_name = data["axsreference"]["numberfield"]
    bcd_field_name = data["axsreference"]["barcodefield"]

    for fname in [org_field_name, loc_field_name, num_field_name, bcd_field_name]:
        if fname not in mapping:
            log.error(f"Field '{fname}' not found in Paperless.")
            return

    custom_fields = []

    # Organisation (select)
    if organisation_label:
        try:
            custom_fields.append(_build_select_field(mapping, org_field_name, organisation_label))
        except ValueError as e:
            log.error(e)
            return

    # Location (select)
    if location_label:
        try:
            custom_fields.append(_build_select_field(mapping, loc_field_name, location_label))
        except ValueError as e:
            log.error(e)
            return

    # Number (integer / text)
    if number_value is not None:
        num_entry = mapping[num_field_name]
        if num_entry["data_type"] not in ("integer", "text"):
            log.warning(f"Field '{num_field_name}' is neither integer nor text � setting value anyway.")
        custom_fields.append({"field": num_entry["field_id"], "value": number_value})

    # Barcode (string)
    if bcd_value is not None:
        bcd_entry = mapping[bcd_field_name]
        if bcd_entry["data_type"] not in ("integer", "text"):
            log.warning(f"Field '{bcd_field_name}' is neither integer nor text � setting value anyway.")
        custom_fields.append({"field": bcd_entry["field_id"], "value": bcd_value})

    # PATCH request
    url     = f"{data['axsreference']['paperlessurl']}/api/documents/{doc_id}/"
    headers = {"Authorization": f"Token {data['axsreference']['apitoken']}"}
    payload = {"custom_fields": custom_fields}

    try:
        response = requests.patch(url, json=payload, headers=headers)
        if response.status_code == 200:
            log.info("Document updated successfully.")
        else:
            log.error(f"API error {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as e:
        log.error(f"PATCH request failed: {e}")


# -----------------------------------------
# MAIN
# -----------------------------------------

def main():
    log.info("axsreference start")

    doc_id    = os.getenv("DOCUMENT_ID")
    file_path = os.getenv("DOCUMENT_PATH")

    if not doc_id or not file_path:
        log.error("Required environment variables DOCUMENT_ID / DOCUMENT_PATH are missing.")
        return

    log.info(f"Scanning file: {file_path}")
    codes = scan_file(file_path)

    if not codes:
        log.info("No barcodes found.")
        return

    log.info(f"Found barcodes: {codes}")

    organisation_label = ""
    location_label     = ""
    number_value       = ""
    bcd_value          = ""
    extra_barcodes     = []

    for code in codes:
        result = get_storage_location(code, data["organisations"], data["locations"])

        if result:
            log.info(
                f"axsreference detected ? "
                f"organisation={result['organisation_name']}, "
                f"location={result['location_name']}, "
                f"number={result['number']}"
            )
            organisation_label = result["organisation_name"]
            location_label     = result["location_name"]
            number_value       = result["number"]

        elif data["axsreference"]["barcodeidentify"]:
            extra_barcodes.append(code)
            log.info(f"Additional barcode detected: {code}")

        bcd_value = " ".join(extra_barcodes) if extra_barcodes else ""


    if all([organisation_label, location_label, number_value]):
        update_document(doc_id, organisation_label, location_label, number_value, bcd_value)

    exit(0)


if __name__ == "__main__":
    main()
