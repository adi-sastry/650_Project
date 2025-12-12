"""
Stage 4 Query Utilities
Comprehensive examples of all supported query patterns for wildlife detection data
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from stage4_metadata_manager import MetadataManager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DetectionQueryUtility:
    """
    Provides convenient query methods for wildlife detection data.
    Demonstrates all supported access patterns.
    """
    
    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize query utility.
        
        Args:
            region: AWS region
        """
        self.manager = MetadataManager(region=region)
        logger.info("DetectionQueryUtility initialized")
    
    # ============================================
    # SPECIES-BASED QUERIES
    # ============================================
    
    def find_all_species_detections(self, species_name: str, days_back: int = 30) -> List[Dict]:
        """
        Find all detections of a specific species within the last N days.
        
        Example: Find all cheetah sightings in the last 30 days
        
        Args:
            species_name: Name of the species (e.g., 'cheetah', 'lion', 'elephant')
            days_back: Number of days to look back
        
        Returns:
            List of detection records
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        results = self.manager.get_detections_by_species(
            species=species_name,
            start_date=start_date.isoformat() + 'Z',
            end_date=end_date.isoformat() + 'Z',
            limit=1000
        )
        
        logger.info(f"Found {len(results)} detections of {species_name} in the last {days_back} days")
        return results
    
    def get_species_distribution(self) -> Dict[str, int]:
        """
        Get count of detections for each species.
        
        Returns:
            Dictionary mapping species name to detection count
        """
        stats = self.manager.get_detection_statistics()
        return stats.get('species_counts', {})
    
    def compare_species_by_time_period(self, species_list: List[str], start_date: str, end_date: str) -> Dict:
        """
        Compare detection counts for multiple species over a time period.
        
        Example: Compare lion vs cheetah sightings in November 2024
        
        Args:
            species_list: List of species names
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
        
        Returns:
            Dictionary with comparison data
        """
        comparison = {}
        
        for species in species_list:
            detections = self.manager.get_detections_by_species(
                species=species,
                start_date=start_date,
                end_date=end_date,
                limit=10000
            )
            
            comparison[species] = {
                'count': len(detections),
                'average_confidence': sum(float(d.get('average_confidence', 0)) for d in detections) / len(detections) if detections else 0,
                'unique_cameras': len(set(d.get('camera_id', 'unknown') for d in detections))
            }
        
        logger.info(f"Compared {len(species_list)} species over time period")
        return comparison
    
    # ============================================
    # DATE/TIME-BASED QUERIES
    # ============================================
    
    def get_detections_today(self) -> List[Dict]:
        """
        Get all detections from today.
        
        Returns:
            List of today's detection records
        """
        today = datetime.utcnow().date()
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        
        return self.manager.get_detections_by_date_range(
            start_date=start.isoformat() + 'Z',
            end_date=end.isoformat() + 'Z',
            limit=1000
        )
    
    def get_detections_this_week(self) -> List[Dict]:
        """
        Get all detections from the current week.
        
        Returns:
            List of this week's detection records
        """
        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday())
        week_start = datetime.combine(week_start.date(), datetime.min.time())
        
        return self.manager.get_detections_by_date_range(
            start_date=week_start.isoformat() + 'Z',
            end_date=today.isoformat() + 'Z',
            limit=10000
        )
    
    def get_detections_by_custom_range(self, start_date: str, end_date: str) -> List[Dict]:
        """
        Get detections for a custom date range.
        
        Args:
            start_date: Start date (ISO format: YYYY-MM-DD)
            end_date: End date (ISO format: YYYY-MM-DD)
        
        Returns:
            List of detection records
        """
        return self.manager.get_detections_by_date_range(
            start_date=start_date + 'T00:00:00Z',
            end_date=end_date + 'T23:59:59Z',
            limit=10000
        )
    
    def get_hourly_detection_pattern(self, days_back: int = 7) -> Dict[int, int]:
        """
        Get detection counts by hour of day over the last N days.
        Useful for understanding wildlife activity patterns.
        
        Args:
            days_back: Number of days to analyze
        
        Returns:
            Dictionary mapping hour (0-23) to detection count
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        detections = self.manager.get_detections_by_date_range(
            start_date=start_date.isoformat() + 'Z',
            end_date=end_date.isoformat() + 'Z',
            limit=10000
        )
        
        hourly_counts = {hour: 0 for hour in range(24)}
        
        for detection in detections:
            try:
                timestamp = detection.get('capture_time') or detection.get('timestamp')
                if timestamp:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    hourly_counts[dt.hour] += 1
            except Exception:
                continue
        
        return hourly_counts
    
    # ============================================
    # CAMERA-BASED QUERIES
    # ============================================
    
    def get_camera_detections(self, camera_id: str, days_back: int = 30) -> List[Dict]:
        """
        Get all detections from a specific camera.
        
        Args:
            camera_id: Camera identifier
            days_back: Number of days to look back
        
        Returns:
            List of detection records
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        return self.manager.get_detections_by_camera(
            camera_id=camera_id,
            start_date=start_date.isoformat() + 'Z',
            end_date=end_date.isoformat() + 'Z',
            limit=1000
        )
    
    def get_camera_performance_metrics(self, camera_id: str) -> Dict:
        """
        Get performance metrics for a specific camera.
        
        Args:
            camera_id: Camera identifier
        
        Returns:
            Dictionary with performance metrics
        """
        detections = self.manager.get_detections_by_camera(
            camera_id=camera_id,
            limit=10000
        )
        
        if not detections:
            return {
                'camera_id': camera_id,
                'total_detections': 0,
                'message': 'No detections found for this camera'
            }
        
        species_counts = {}
        total_confidence = 0
        
        for det in detections:
            species = det.get('species', 'unknown')
            species_counts[species] = species_counts.get(species, 0) + 1
            total_confidence += float(det.get('average_confidence', 0))
        
        return {
            'camera_id': camera_id,
            'total_detections': len(detections),
            'unique_species': len(species_counts),
            'species_breakdown': species_counts,
            'average_confidence': total_confidence / len(detections),
            'most_detected_species': max(species_counts, key=species_counts.get) if species_counts else None,
            'first_detection': min(d.get('timestamp', '') for d in detections),
            'last_detection': max(d.get('timestamp', '') for d in detections)
        }
    
    def compare_cameras(self, camera_ids: List[str]) -> Dict:
        """
        Compare performance across multiple cameras.
        
        Args:
            camera_ids: List of camera identifiers
        
        Returns:
            Dictionary with comparison data
        """
        comparison = {}
        
        for camera_id in camera_ids:
            comparison[camera_id] = self.get_camera_performance_metrics(camera_id)
        
        return comparison
    
    # ============================================
    # GEOGRAPHIC QUERIES
    # ============================================
    
    def find_detections_in_region(self, lat_min: float, lat_max: float, 
                                   lon_min: float, lon_max: float) -> List[Dict]:
        """
        Find all detections within a geographic bounding box.
        
        Example: Find all wildlife in Maasai Mara region
        lat_min=-1.5, lat_max=-1.0, lon_min=35.0, lon_max=35.5
        
        Args:
            lat_min: Minimum latitude
            lat_max: Maximum latitude
            lon_min: Minimum longitude
            lon_max: Maximum longitude
        
        Returns:
            List of detection records
        """
        return self.manager.get_detections_by_geographic_region(
            lat_min=lat_min,
            lat_max=lat_max,
            lon_min=lon_min,
            lon_max=lon_max,
            limit=10000
        )
    
    def get_species_geographic_distribution(self, species: str) -> Dict:
        """
        Get geographic distribution of a species.
        
        Args:
            species: Species name
        
        Returns:
            Dictionary with geographic data
        """
        detections = self.manager.get_detections_by_species(species=species, limit=10000)
        
        if not detections:
            return {'species': species, 'locations': [], 'message': 'No detections found'}
        
        locations = []
        for det in detections:
            locations.append({
                'latitude': float(det.get('latitude', 0)),
                'longitude': float(det.get('longitude', 0)),
                'timestamp': det.get('timestamp'),
                'confidence': float(det.get('average_confidence', 0))
            })
        
        # Calculate centroid
        avg_lat = sum(loc['latitude'] for loc in locations) / len(locations)
        avg_lon = sum(loc['longitude'] for loc in locations) / len(locations)
        
        return {
            'species': species,
            'total_sightings': len(locations),
            'locations': locations,
            'centroid': {'latitude': avg_lat, 'longitude': avg_lon}
        }
    
    # ============================================
    # CONFIDENCE-BASED QUERIES
    # ============================================
    
    def get_high_confidence_detections(self, min_confidence: float = 0.9) -> List[Dict]:
        """
        Get all high-confidence detections.
        
        Args:
            min_confidence: Minimum confidence threshold (0.0-1.0)
        
        Returns:
            List of high-confidence detections
        """
        return self.manager.get_high_confidence_detections(
            min_confidence=min_confidence,
            limit=1000
        )
    
    def get_low_confidence_detections_for_review(self, max_confidence: float = 0.5) -> List[Dict]:
        """
        Get low-confidence detections that may need manual review.
        
        Args:
            max_confidence: Maximum confidence threshold
        
        Returns:
            List of low-confidence detections
        """
        # Use scan with filter for low confidence
        try:
            from boto3.dynamodb.conditions import Attr
            from decimal import Decimal
            
            table = self.manager.detection_results_table or self.manager.dynamodb.Table('detection_results')
            
            response = table.scan(
                FilterExpression=Attr('average_confidence').lte(Decimal(str(max_confidence))),
                Limit=1000
            )
            
            results = response.get('Items', [])
            logger.info(f"Found {len(results)} low-confidence detections for review")
            return results
            
        except Exception as e:
            logger.error(f"Error querying low-confidence detections: {e}")
            return []
    
    # ============================================
    # UNPROCESSED IMAGE QUERIES
    # ============================================
    
    def get_unprocessed_images_count(self) -> int:
        """
        Get count of images waiting to be processed.
        
        Returns:
            Number of unprocessed images
        """
        unprocessed = self.manager.get_unprocessed_images(limit=10000)
        return len(unprocessed)
    
    def get_oldest_unprocessed_images(self, limit: int = 10) -> List[Dict]:
        """
        Get the oldest unprocessed images (processing queue).
        
        Args:
            limit: Number of images to return
        
        Returns:
            List of oldest unprocessed images
        """
        return self.manager.get_unprocessed_images(limit=limit)
    
    # ============================================
    # ADVANCED ANALYTICS QUERIES
    # ============================================
    
    def get_detection_trends(self, days: int = 30, interval: str = 'daily') -> Dict:
        """
        Get detection trends over time.
        
        Args:
            days: Number of days to analyze
            interval: 'daily', 'weekly', or 'monthly'
        
        Returns:
            Dictionary with trend data
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        detections = self.manager.get_detections_by_date_range(
            start_date=start_date.isoformat() + 'Z',
            end_date=end_date.isoformat() + 'Z',
            limit=10000
        )
        
        trends = {}
        
        for detection in detections:
            timestamp = detection.get('timestamp', '')
            if not timestamp:
                continue
            
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                if interval == 'daily':
                    key = dt.strftime('%Y-%m-%d')
                elif interval == 'weekly':
                    key = dt.strftime('%Y-W%U')
                elif interval == 'monthly':
                    key = dt.strftime('%Y-%m')
                else:
                    key = dt.strftime('%Y-%m-%d')
                
                if key not in trends:
                    trends[key] = {
                        'count': 0,
                        'species': set(),
                        'cameras': set()
                    }
                
                trends[key]['count'] += 1
                trends[key]['species'].add(detection.get('species', 'unknown'))
                trends[key]['cameras'].add(detection.get('camera_id', 'unknown'))
            
            except Exception:
                continue
        
        # Convert sets to counts
        for key in trends:
            trends[key]['unique_species'] = len(trends[key]['species'])
            trends[key]['unique_cameras'] = len(trends[key]['cameras'])
            del trends[key]['species']
            del trends[key]['cameras']
        
        return trends
    
    def get_rare_species_alerts(self, threshold: int = 5) -> List[Dict]:
        """
        Get species that have been detected fewer than threshold times (rare sightings).
        
        Args:
            threshold: Maximum detection count to be considered rare
        
        Returns:
            List of rare species with their detection data
        """
        stats = self.manager.get_detection_statistics()
        species_counts = stats.get('species_counts', {})
        
        rare_species = []
        
        for species, count in species_counts.items():
            if count <= threshold and species != 'unknown':
                detections = self.manager.get_detections_by_species(species=species, limit=100)
                rare_species.append({
                    'species': species,
                    'detection_count': count,
                    'detections': detections
                })
        
        logger.info(f"Found {len(rare_species)} rare species (threshold: {threshold})")
        return rare_species
    
    def export_detections_to_csv(self, output_file: str, filters: Optional[Dict] = None) -> bool:
        """
        Export detection data to CSV file.
        
        Args:
            output_file: Path to output CSV file
            filters: Optional filters (species, date_range, camera_id, etc.)
        
        Returns:
            bool: True if successful
        """
        import csv
        
        try:
            # Get detections based on filters
            if filters:
                if 'species' in filters:
                    detections = self.manager.get_detections_by_species(
                        species=filters['species'],
                        limit=10000
                    )
                elif 'camera_id' in filters:
                    detections = self.manager.get_detections_by_camera(
                        camera_id=filters['camera_id'],
                        limit=10000
                    )
                else:
                    stats = self.manager.get_detection_statistics()
                    detections = []  # Would need to implement full scan
            else:
                stats = self.manager.get_detection_statistics()
                detections = []  # Would need to implement full scan
            
            if not detections:
                logger.warning("No detections to export")
                return False
            
            # Write to CSV
            with open(output_file, 'w', newline='') as csvfile:
                fieldnames = ['detection_id', 'timestamp', 'species', 'confidence', 
                             'camera_id', 'latitude', 'longitude', 'image_name']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for det in detections:
                    writer.writerow({
                        'detection_id': det.get('detection_id', ''),
                        'timestamp': det.get('timestamp', ''),
                        'species': det.get('species', ''),
                        'confidence': float(det.get('average_confidence', 0)),
                        'camera_id': det.get('camera_id', ''),
                        'latitude': float(det.get('latitude', 0)),
                        'longitude': float(det.get('longitude', 0)),
                        'image_name': det.get('image_name', '')
                    })
            
            logger.info(f"Exported {len(detections)} detections to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return False


def demo_all_queries():
    """
    Demonstrate all query capabilities.
    """
    print("=" * 60)
    print("Stage 4 Query Utility - Comprehensive Demo")
    print("=" * 60)
    
    query_util = DetectionQueryUtility()
    
    # Species queries
    print("\n1. SPECIES-BASED QUERIES")
    print("-" * 60)
    cheetah_detections = query_util.find_all_species_detections('cheetah', days_back=30)
    print(f"Cheetah detections (last 30 days): {len(cheetah_detections)}")
    
    species_dist = query_util.get_species_distribution()
    print(f"Species distribution: {species_dist}")
    
    # Date queries
    print("\n2. DATE/TIME-BASED QUERIES")
    print("-" * 60)
    today_detections = query_util.get_detections_today()
    print(f"Detections today: {len(today_detections)}")
    
    hourly_pattern = query_util.get_hourly_detection_pattern(days_back=7)
    print(f"Hourly detection pattern: {hourly_pattern}")
    
    # Camera queries
    print("\n3. CAMERA-BASED QUERIES")
    print("-" * 60)
    camera_metrics = query_util.get_camera_performance_metrics('CAM_001')
    print(f"Camera CAM_001 metrics: {camera_metrics}")
    
    # Geographic queries
    print("\n4. GEOGRAPHIC QUERIES")
    print("-" * 60)
    region_detections = query_util.find_detections_in_region(
        lat_min=-1.5, lat_max=-1.0, lon_min=35.0, lon_max=35.5
    )
    print(f"Detections in region: {len(region_detections)}")
    
    # Confidence queries
    print("\n5. CONFIDENCE-BASED QUERIES")
    print("-" * 60)
    high_conf = query_util.get_high_confidence_detections(min_confidence=0.9)
    print(f"High-confidence detections (>0.9): {len(high_conf)}")
    
    # Advanced analytics
    print("\n6. ADVANCED ANALYTICS")
    print("-" * 60)
    trends = query_util.get_detection_trends(days=30, interval='daily')
    print(f"Daily trends (last 30 days): {len(trends)} data points")
    
    rare_species = query_util.get_rare_species_alerts(threshold=5)
    print(f"Rare species (≤5 detections): {len(rare_species)}")
    
    print("\n" + "=" * 60)
    print("Demo complete! All query patterns demonstrated.")
    print("=" * 60)


if __name__ == "__main__":
    demo_all_queries()
