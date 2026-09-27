import pytest
from src.ingestion.parser import normalize_station_name

def test_normalize_station_name():
    assert normalize_station_name("gurgaon") == "GURUGRAM"
    assert normalize_station_name("  Gurgaon Bus Stand  ") == "GURUGRAM"
    assert normalize_station_name("delhi") == "DELHI (ISBT)"
    assert normalize_station_name("ISBT KASHMERE GATE") == "DELHI (ISBT)"
    assert normalize_station_name("  chandigarh sec 17 - ") == "CHANDIGARH"
    assert normalize_station_name("ambala cantt") == "AMBALA CANTT"
    assert normalize_station_name("") == ""
    assert normalize_station_name("-") == ""
