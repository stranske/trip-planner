"""Source adapter interfaces."""

from .amtrak_gtfs import AmtrakGtfsAdapter
from .base import SourceAdapter
from .duffel_flight import DuffelFlightAdapter

__all__ = ["AmtrakGtfsAdapter", "DuffelFlightAdapter", "SourceAdapter"]
