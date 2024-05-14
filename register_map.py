'''
gender => gender
foldEar => ear_folded
neutralization_code => neutering_surgery
body_form_code => body_shape
disease_treat_code => disease_treatment
conditions_code => energetic
appetite_change_code => appetite
feed_amount_code => pet_food
snack => treat
drinking_amount_code => water_intake
how_to_know_allergy_code => allergy_detect
walk_code => daily_walk
main_act_place_code => living_space
relationship_code => multi_animal_environment

gender_female, 'F'
gender_male, 'M'
ear_folded_yes, 'Y'
ear_folded_no, 'N'
neutering_surgery_performed, 0
neutering_surgery_planned, 1
neutering_surgery_not_planned, 2
body_shape_underweight_severe, 0
body_shape_underweight_slight, 1
body_shape_normal, 2
body_shape_overweight_slight, 3
body_shape_obese_severe, 4
disease_treatment_ongoing, 0
disease_treatment_diagnosed_only, 1
energetic_stable, 0
energetic_slightly_decreased, 1
energetic_significantly_decreased, 2
appetite_decreased, 0
appetite_unchanged, 1
appetite_increased, 2
pet_food_low, 0
pet_food_normal, 1
pet_food_high, 2
pet_food_excessive, 3
treat_yes, 'Y'
treat_no, 'N'
water_intake_recommended_amount, 0
water_intake_more_than_recommended, 1
water_intake_less_than_recommended, 2
water_intake_less_for_weight_loss, 3
allergy_detect_diagnosed, 0
allergy_detect_suspected, 1
daily_walk_once_a_day, 0
daily_walk_twice_a_day, 1
daily_walk_more_than_three_times_a_day, 2
daily_walk_not_every_day, 3
living_space_indoor_apartment, 0
living_space_indoor_with_yard, 1
living_space_indoor_without_yard, 2 
living_space_indoor_outdoor, 3
multi_animal_environment_no, 0
multi_animal_environment_two_animal, 1
multi_animal_environment_more_than_three_animal, 2
'''
health_map = {
    "gender_female": 'F',
    "gender_male": 'M',
    "ear_folded_yes": 'Y',
    "ear_folded_no": 'N',
    "neutering_surgery_performed": '0',
    "neutering_surgery_planned": '1',
    "neutering_surgery_not_planned": '2',
    "body_shape_underweight_severe": '0',
    "body_shape_underweight_slight": '1',
    "body_shape_normal": '2',
    "body_shape_overweight_slight": '3',
    "body_shape_obese_severe": '4',
    "disease_treatment_ongoing": '0',
    "disease_treatment_diagnosed_only": '1',
    "energetic_stable": '0',
    "energetic_slightly_decreased": '1',
    "energetic_significantly_decreased": '2',
    "appetite_decreased": '0',
    "appetite_unchanged": '1',
    "appetite_increased": '2',
    "pet_food_recommended_amount": "0",
    "pet_food_more_than_recommended": "1",
    "pet_food_less_than_recommended": "2",
    "pet_food_less_for_weight_loss": "3",
    "pet_food_approximate_amount": "4",
    "pet_food_self_regulated": "5",
    "treat_yes": 'Y',
    "treat_no": 'N',
    "water_intake_low": '0',
    "water_intake_normal": '1',
    "water_intake_high": '2',
    "water_intake_excessive": '3',
    "allergy_detect_diagnosed": '0',
    "allergy_detect_suspected": '1',
    "daily_walk_once_a_day": '0',
    "daily_walk_twice_a_day": '1',
    "daily_walk_more_than_three_times_a_day": '2',
    "daily_walk_not_every_day": '3',
    "living_space_indoor_apartment": '0',
    "living_space_indoor_with_yard": '1',
    "living_space_indoor_without_yard": '2',
    "living_space_outdoor": '3',
    "multi_animal_environment_no": '0',
    "multi_animal_environment_two_animal": '1',
    "multi_animal_environment_more_than_three_animal": '2'
}
