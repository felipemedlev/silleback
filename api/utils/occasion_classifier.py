"""
Accord-based Occasion Classification System

This module provides logic to classify perfumes into occasions based on their accords.
Maps perfume accords to appropriate occasions using weighted scoring.
"""

from typing import List, Dict, Tuple
from collections import defaultdict


class AccordOccasionClassifier:
    """
    Classifies perfumes into occasions based on their accord profiles.
    """

    # Accord-to-occasion mappings with weights
    # Higher weight = stronger association with that occasion
    ACCORD_OCCASION_MAP = {
        # Deporte (Sport) - Fresh, clean, energetic
        'Deporte': {
            'fresh': 3.0,
            'citrus': 3.0,
            'aquatic': 3.0,
            'aromatic': 2.5,
            'green': 2.5,
            'herbal': 2.5,
            'marine': 3.0,
            'ozonic': 2.5,
            'fruity': 1.5,
            'woody': 1.0,
        },

        # Oficina (Office) - Professional, clean, not overpowering
        'Oficina': {
            'powdery': 3.0,
            'woody': 2.5,
            'iris': 2.5,
            'soft spicy': 2.5,
            'musky': 2.0,
            'fresh spicy': 2.0,
            'fresh': 2.0,
            'aromatic': 2.0,
            'citrus': 1.5,
            'amber': 1.5,
            'floral': 1.5,
            'violet': 2.0,
        },

        # Casual - Easy-going, versatile, everyday
        'Casual': {
            'fruity': 3.0,
            'sweet': 2.5,
            'vanilla': 2.5,
            'citrus': 2.5,
            'fresh': 2.5,
            'aromatic': 2.0,
            'floral': 2.0,
            'green': 2.0,
            'lavender': 2.0,
            'coconut': 2.5,
        },

        # Fiesta (Party) - Sweet, gourmand, festive
        'Fiesta': {
            'sweet': 3.0,
            'fruity': 2.5,
            'caramel': 3.0,
            'cacao': 3.0,
            'rum': 3.0,
            'warm spicy': 2.5,
            'amber': 2.0,
            'vanilla': 2.5,
            'chocolate': 3.0,
            'coffee': 2.5,
            'honey': 2.5,
            'almond': 2.5,
        },

        # Sexy - Intense, warm, sensual
        'Sexy': {
            'animalic': 3.0,
            'leather': 3.0,
            'oud': 2.5,
            'amber': 2.5,
            'warm spicy': 2.5,
            'musky': 2.5,
            'sweet': 2.0,
            'vanilla': 2.0,
            'oriental': 2.5,
            'spicy': 2.5,
            'smoky': 2.0,
            'patchouli': 2.0,
        },

        # Formal - Sophisticated, elegant, refined
        'Formal': {
            'woody': 3.0,
            'oud': 3.0,
            'leather': 2.5,
            'powdery': 2.5,
            'iris': 3.0,
            'smoky': 2.5,
            'tobacco': 3.0,
            'amber': 2.0,
            'rose': 2.0,
            'incense': 2.5,
            'vetiver': 2.5,
            'cedar': 2.5,
        },

        # Especial (Special) - Unique, floral, distinctive
        'Especial': {
            'rose': 3.0,
            'white floral': 3.0,
            'iris': 2.5,
            'violet': 2.5,
            'jasmine': 3.0,
            'tuberose': 3.0,
            'ylang-ylang': 2.5,
            'narcissus': 2.5,
            'orange blossom': 2.5,
            'orchid': 2.5,
            'gardenia': 2.5,
        },
    }

    # Viaje (Travel) is special - only assigned to balanced, versatile perfumes
    # We'll calculate this separately

    def __init__(self, min_occasions: int = 1, max_occasions: int = 3, score_threshold: float = 4.0):
        """
        Initialize the classifier.

        Args:
            min_occasions: Minimum number of occasions to assign per perfume
            max_occasions: Maximum number of occasions to assign per perfume
            score_threshold: Minimum score required to assign an occasion
        """
        self.min_occasions = min_occasions
        self.max_occasions = max_occasions
        self.score_threshold = score_threshold

    def classify_perfume(self, accords: List[Tuple[str, int]]) -> List[str]:
        """
        Classify a perfume into occasions based on its accords.

        Args:
            accords: List of (accord_name, position) tuples, where position is 0-based
                    (0 = primary accord, 1 = secondary, etc.)

        Returns:
            List of occasion names suitable for this perfume
        """
        if not accords:
            return ['Casual']  # Default for perfumes without accords

        # Calculate weighted scores for each occasion
        occasion_scores = defaultdict(float)

        for accord_name, position in accords:
            # Position weight: primary=3, secondary=2, tertiary+=1
            position_weight = max(3 - position, 1)

            # Add weighted score for each occasion that matches this accord
            for occasion, accord_weights in self.ACCORD_OCCASION_MAP.items():
                if accord_name.lower() in accord_weights:
                    base_weight = accord_weights[accord_name.lower()]
                    occasion_scores[occasion] += base_weight * position_weight

        # Sort occasions by score
        sorted_occasions = sorted(
            occasion_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Select top occasions above threshold
        selected_occasions = []
        for occasion, score in sorted_occasions:
            if score >= self.score_threshold and len(selected_occasions) < self.max_occasions:
                selected_occasions.append(occasion)

        # Ensure minimum occasions - but only if we found ANY matches above a lower threshold
        lower_threshold = self.score_threshold * 0.6
        if len(selected_occasions) < self.min_occasions:
            for occasion, score in sorted_occasions:
                if occasion not in selected_occasions and score >= lower_threshold:
                    selected_occasions.append(occasion)
                    if len(selected_occasions) >= self.min_occasions:
                        break

        # If still no occasions (shouldn't happen), default to Casual
        if not selected_occasions:
            selected_occasions = ['Casual']

        # Determine if perfume should be marked as "Viaje" (Travel)
        # Only if it has balanced scores across multiple occasions
        # or has fresh/versatile accords
        if self._is_travel_suitable(accords, occasion_scores, selected_occasions):
            # Add Viaje only if we have room, don't replace existing occasions
            if len(selected_occasions) < self.max_occasions:
                selected_occasions.append('Viaje')

        return selected_occasions

    def _is_travel_suitable(
        self,
        accords: List[Tuple[str, int]],
        occasion_scores: Dict[str, float],
        selected_occasions: List[str]
    ) -> bool:
        """
        Determine if a perfume is suitable for travel.
        Travel perfumes should be versatile and not too polarizing.
        Be very selective - only truly versatile perfumes.
        """
        if not accords or len(selected_occasions) < 2:
            return False

        # Check if perfume has versatile/fresh accords in TOP 3
        versatile_accords = {'fresh', 'citrus', 'aromatic', 'woody'}
        top_accord_names = {acc[0].lower() for acc in accords[:3]}

        has_versatile = len(top_accord_names & versatile_accords) >= 2

        # Must NOT have polarizing accords in primary position
        polarizing_accords = {'oud', 'leather', 'animalic', 'tobacco', 'smoky'}
        has_polarizing_primary = accords[0][0].lower() in polarizing_accords if accords else False

        if has_polarizing_primary:
            return False

        # Check if occasion scores are balanced (no single dominant occasion)
        if len(occasion_scores) >= 3:
            sorted_scores = sorted(occasion_scores.values(), reverse=True)
            if len(sorted_scores) >= 3:
                # Top score should not dominate - must have good scores across occasions
                top_score = sorted_scores[0]
                third_score = sorted_scores[2]
                # Third score should be at least 50% of top score
                is_balanced = third_score / top_score >= 0.5 if top_score > 0 else False

                return has_versatile and is_balanced

        return False

    def get_occasion_summary(self, accords: List[Tuple[str, int]]) -> Dict[str, float]:
        """
        Get detailed scoring breakdown for debugging/analysis.

        Args:
            accords: List of (accord_name, position) tuples

        Returns:
            Dictionary of occasion -> score
        """
        occasion_scores = defaultdict(float)

        for accord_name, position in accords:
            position_weight = max(3 - position, 1)

            for occasion, accord_weights in self.ACCORD_OCCASION_MAP.items():
                if accord_name.lower() in accord_weights:
                    base_weight = accord_weights[accord_name.lower()]
                    occasion_scores[occasion] += base_weight * position_weight

        return dict(occasion_scores)
