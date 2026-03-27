from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import current_user, login_required
from app.extensions import db
from app.models import CarbonLog
from app.forms import CarbonEntryForm
from app.utils.carbon import calculate_emissions
from app.utils.ai import calculate_ai_emissions
from app.utils.game import classify_green_log, calculate_boss_impact, update_streak

bp = Blueprint('logger', __name__)

@bp.route('/log-entry', methods=['GET', 'POST'])
@login_required
def log_entry():
    form = CarbonEntryForm()
    if request.method == 'POST':
        try:
            if 'voice_input' in request.form:
                activity_text = request.form.get('voice_transcript')
                if activity_text:
                    try:
                        ai_result = calculate_ai_emissions(activity_text)
                        ai_emissions = ai_result['total_kg']
                        metadata = ai_result['metadata']
                        
                        new_log = CarbonLog(
                            user_id=current_user.id,
                            activity_type='voice_input',
                            description=activity_text,
                            transport_type=metadata.get('transport_type'),
                            diet_type=metadata.get('diet_type'),
                            distance=metadata.get('distance_km'),
                            ai_calculated_emissions=ai_emissions,
                            total_emissions=ai_emissions
                        )
                        db.session.add(new_log)
                        current_user.total_points += 10
                        current_user.carbon_score += ai_emissions
                        
                        green = classify_green_log(
                            transport_type=metadata.get('transport_type'),
                            diet_type=metadata.get('diet_type'),
                            total_emissions=ai_emissions
                        )
                        if green['is_green']:
                            current_user.total_points += green['bonus']
                        update_streak(current_user)
                        db.session.commit()
                        
                        impact = calculate_boss_impact(
                            transport_type=metadata.get('transport_type'),
                            diet_type=metadata.get('diet_type'),
                            total_emissions=ai_emissions,
                            streak=current_user.streak or 0
                        )
                        flash(f'Voice activity logged! Emissions: {ai_emissions:.2f} kg CO₂', 'success')
                        if impact['is_heal']:
                            flash(f'💀 The Smog Boss healed {abs(impact["total"])} HP from your emissions!', 'warning')
                        else:
                            flash(f'⚔️ You dealt {impact["total"]} HP damage to the Smog Boss!', 'success')
                        if green['is_green']:
                            flash(f'🌿 GREEN LOG! +{green["bonus"]} bonus points — {", ".join(green["reasons"])}', 'success')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error processing voice input: {str(e)}', 'danger')
                else:
                    flash('No voice input received. Please try again.', 'warning')

            elif request.form.get('custom_activity'):
                activity_text = request.form.get('custom_activity', '').strip()
                if activity_text:
                    ai_result = calculate_ai_emissions(activity_text)
                    ai_emissions = ai_result['total_kg']
                    metadata = ai_result['metadata']
                    
                    new_log = CarbonLog(
                        user_id=current_user.id,
                        activity_type='custom',
                        description=activity_text,
                        transport_type=metadata.get('transport_type'),
                        diet_type=metadata.get('diet_type'),
                        distance=metadata.get('distance_km'),
                        ai_calculated_emissions=ai_emissions,
                        total_emissions=ai_emissions
                    )
                    db.session.add(new_log)
                    current_user.total_points += 10
                    current_user.carbon_score += ai_emissions
                    
                    green = classify_green_log(
                        transport_type=metadata.get('transport_type'),
                        diet_type=metadata.get('diet_type'),
                        total_emissions=ai_emissions
                    )
                    if green['is_green']:
                        current_user.total_points += green['bonus']
                    update_streak(current_user)
                    db.session.commit()
                    
                    impact = calculate_boss_impact(
                        transport_type=metadata.get('transport_type'),
                        diet_type=metadata.get('diet_type'),
                        total_emissions=ai_emissions,
                        streak=current_user.streak or 0
                    )
                    flash(f'Custom activity logged! Emissions: {ai_emissions:.2f} kg CO₂', 'success')
                    if impact['is_heal']:
                        flash(f'💀 The Smog Boss healed {abs(impact["total"])} HP from your emissions!', 'warning')
                    else:
                        flash(f'⚔️ You dealt {impact["total"]} HP damage to the Smog Boss!', 'success')
                    if green['is_green']:
                        flash(f'🌿 GREEN LOG! +{green["bonus"]} bonus points — {", ".join(green["reasons"])}', 'success')
                else:
                    flash('Please provide a description of your activity.', 'warning')

            else:
                # Standard Log — category-aware processing
                category = request.form.get('activity_category', 'transport')
                
                # Build form_data dict based on activity category
                form_data = {
                    'transport_type': None,
                    'distance': 0,
                    'fuel_type': None,
                    'fuel_liters': 0,
                    'energy_usage': 0,
                    'diet_type': None
                }
                
                if category == 'transport':
                    transport_type = request.form.get('transport_type', 'car')
                    distance = request.form.get('distance', '')
                    if not transport_type or not distance:
                        flash('Please select a transport type and enter a distance.', 'warning')
                        return render_template('log_entry.html', form=form)
                    form_data['transport_type'] = transport_type
                    form_data['distance'] = float(distance)
                    form_data['fuel_type'] = request.form.get('fuel_type')
                    form_data['fuel_liters'] = float(request.form.get('fuel_liters') or 0)
                    
                elif category == 'food':
                    diet_type = request.form.get('diet_type', '')
                    if not diet_type:
                        flash('Please select a diet type.', 'warning')
                        return render_template('log_entry.html', form=form)
                    form_data['diet_type'] = diet_type
                    
                elif category == 'energy':
                    energy_usage = request.form.get('energy_usage', '')
                    if not energy_usage:
                        flash('Please enter your energy usage in kWh.', 'warning')
                        return render_template('log_entry.html', form=form)
                    form_data['energy_usage'] = float(energy_usage)

                transport_emissions, energy_emissions, diet_emissions, total = calculate_emissions(form_data)
                
                new_log = CarbonLog(
                    user_id=current_user.id,
                    activity_type=category,
                    transport_type=form_data.get('transport_type'),
                    distance=form_data.get('distance') or None,
                    energy_usage=form_data.get('energy_usage') or None,
                    diet_type=form_data.get('diet_type'),
                    transport_emissions=transport_emissions,
                    energy_emissions=energy_emissions,
                    diet_emissions=diet_emissions,
                    total_emissions=total
                )
                db.session.add(new_log)
                current_user.total_points += 10
                current_user.carbon_score += total
                
                green = classify_green_log(form_data.get('transport_type'), form_data.get('diet_type'), total)
                if green['is_green']:
                    current_user.total_points += green['bonus']
                update_streak(current_user)
                db.session.commit()
                
                impact = calculate_boss_impact(form_data.get('transport_type'), form_data.get('diet_type'), total, current_user.streak or 0)
                flash(f'Activity logged! Emissions: {total:.2f} kg CO₂', 'success')
                if impact['is_heal']:
                    flash(f'💀 The Smog Boss healed {abs(impact["total"])} HP from your emissions!', 'warning')
                else:
                    flash(f'⚔️ You dealt {impact["total"]} HP damage to the Smog Boss!', 'success')
                if green['is_green']:
                    flash(f'🌿 GREEN LOG! +{green["bonus"]} bonus points — {", ".join(green["reasons"])}', 'success')
            
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error logging activity: {str(e)}', 'danger')
    
    return render_template('log_entry.html', form=form)
