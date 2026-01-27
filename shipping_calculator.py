"""
Shipping Calculator Module
Calculates actual driving distance between ZIP codes and shipping costs.
Uses OSRM (Open Source Routing Machine) for real road distances.
"""

import pgeocode
import requests

# Default origin ZIP (Steelstack warehouse)
DEFAULT_ORIGIN_ZIP = "37357"

# Shipping rate per mile
RATE_PER_MILE = 3.85

# Minimum shipping cost
MINIMUM_SHIPPING_COST = 1200.00

# OSRM demo server for driving distance (free, no API key needed)
OSRM_URL = "http://router.project-osrm.org/route/v1/driving"


def get_distance_between_zips(origin_zip: str, destination_zip: str) -> dict:
    """
    Calculate the actual driving distance in miles between two US ZIP codes.

    Args:
        origin_zip: Origin ZIP code (5 digits)
        destination_zip: Destination ZIP code (5 digits)

    Returns:
        dict with keys: success, distance_miles, origin_city, origin_state,
                       destination_city, destination_state, error
    """
    try:
        # Initialize US geocoder to get coordinates and city info
        nomi = pgeocode.Nominatim('us')

        # Get location info for both ZIP codes
        origin_info = nomi.query_postal_code(origin_zip)
        dest_info = nomi.query_postal_code(destination_zip)

        # Check if ZIP codes are valid
        if origin_info.empty or str(origin_info.get('place_name', '')) == 'nan':
            return {
                'success': False,
                'error': f'Invalid origin ZIP code: {origin_zip}'
            }

        if dest_info.empty or str(dest_info.get('place_name', '')) == 'nan':
            return {
                'success': False,
                'error': f'Invalid destination ZIP code: {destination_zip}'
            }

        # Get coordinates
        origin_lat = float(origin_info.get('latitude'))
        origin_lon = float(origin_info.get('longitude'))
        dest_lat = float(dest_info.get('latitude'))
        dest_lon = float(dest_info.get('longitude'))

        # Call OSRM for actual driving distance
        url = f"{OSRM_URL}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}?overview=false"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 'Ok' and data.get('routes'):
                # Distance is returned in meters
                distance_meters = data['routes'][0]['distance']
                distance_miles = distance_meters / 1609.344  # meters to miles
            else:
                return {
                    'success': False,
                    'error': 'Could not calculate driving route'
                }
        else:
            return {
                'success': False,
                'error': 'Routing service unavailable'
            }

        return {
            'success': True,
            'distance_miles': round(distance_miles, 1),
            'origin_zip': origin_zip,
            'origin_city': str(origin_info.get('place_name', '')),
            'origin_state': str(origin_info.get('state_code', '')),
            'destination_zip': destination_zip,
            'destination_city': str(dest_info.get('place_name', '')),
            'destination_state': str(dest_info.get('state_code', ''))
        }

    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': 'Routing service timeout - please try again'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def calculate_shipping_cost(origin_zip: str, destination_zip: str, rate_per_mile: float = RATE_PER_MILE) -> dict:
    """
    Calculate shipping cost based on distance between ZIP codes.

    Args:
        origin_zip: Origin ZIP code
        destination_zip: Destination ZIP code
        rate_per_mile: Cost per mile (default: $3.85)

    Returns:
        dict with distance info plus shipping_cost
    """
    result = get_distance_between_zips(origin_zip, destination_zip)

    if result['success']:
        calculated_cost = result['distance_miles'] * rate_per_mile
        # Enforce minimum shipping cost
        shipping_cost = max(calculated_cost, MINIMUM_SHIPPING_COST)
        result['rate_per_mile'] = rate_per_mile
        result['calculated_cost'] = round(calculated_cost, 2)
        result['shipping_cost'] = round(shipping_cost, 2)
        result['minimum_applied'] = shipping_cost > calculated_cost
        result['shipping_description'] = f"Shipping {result['origin_state']} > {result['destination_state']}"

    return result


if __name__ == "__main__":
    # Test the calculator
    print("Testing shipping calculator...\n")

    # Test: Lebanon, TN to various destinations
    test_destinations = [
        ("37087", "90210"),  # TN to Beverly Hills, CA
        ("37087", "10001"),  # TN to New York, NY
        ("37087", "33101"),  # TN to Miami, FL
        ("37087", "75201"),  # TN to Dallas, TX
        ("37087", "98101"),  # TN to Seattle, WA
        ("37087", "23219"),  # TN to Richmond, VA
    ]

    for origin, dest in test_destinations:
        result = calculate_shipping_cost(origin, dest)
        if result['success']:
            print(f"{result['origin_city']}, {result['origin_state']} -> {result['destination_city']}, {result['destination_state']}")
            print(f"  Distance: {result['distance_miles']} miles")
            print(f"  Shipping Cost: ${result['shipping_cost']:,.2f} (@ ${result['rate_per_mile']}/mile)")
            print()
        else:
            print(f"Error: {result['error']}")
