import os
import logging
from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timedelta
import re
from sqlalchemy import func
import csv
import io
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)

# Configuration
app.secret_key = os.environ.get("SESSION_SECRET")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Add custom template filter for newlines
@app.template_filter('nl2br')
def nl2br(value):
    if not value:
        return ""
    return value.replace('\n', '<br>')

db.init_app(app)

from models import Ticket
from agent import ITSupportAgent
from notifications import notify_support_team

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit_ticket', methods=['POST'])
def submit_ticket():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        description = request.form.get('description')
        category = request.form.get('category', 'uncategorized')

        if not all([name, email, description]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('index'))

        # Initialize IT Support Agent
        support_agent = ITSupportAgent()

        # Get agent's response and confidence
        response, confidence, auto_category = support_agent.analyze_ticket(description)

        # Determine if human attention is needed based on confidence
        requires_human = confidence < 0.7

        # Create ticket with enhanced fields
        ticket = Ticket(
            name=name,
            email=email,
            description=description,
            category=auto_category or category,
            status="pending_review" if requires_human else "open",
            ai_response=response,
            confidence_score=confidence,
            requires_human_attention=requires_human
        )

        db.session.add(ticket)
        db.session.commit()

        # Notify support team if confidence is low
        if requires_human:
            notify_support_team(ticket)
            flash('Your ticket has been escalated to our support team.', 'info')

        # Redirect to chat interface
        return redirect(url_for('chat_view', ticket_id=ticket.id))

    except Exception as e:
        logger.error(f"Error processing ticket: {str(e)}")
        db.session.rollback()
        flash('An error occurred while processing your request.', 'error')
        return redirect(url_for('index'))

@app.route('/chat/<int:ticket_id>')
def chat_view(ticket_id):
    try:
        ticket = Ticket.query.get_or_404(ticket_id)
        return render_template('chat.html', ticket=ticket)
    except Exception as e:
        logger.error(f"Error accessing chat view: {str(e)}")
        flash('Error accessing chat interface.', 'error')
        return redirect(url_for('index'))

@app.route('/chat_message', methods=['POST'])
def chat_message():
    try:
        data = request.get_json()
        ticket_id = data.get('ticket_id')
        user_message = data.get('message')

        if not all([ticket_id, user_message]):
            return jsonify({'error': 'Missing required fields'}), 400

        ticket = Ticket.query.get_or_404(ticket_id)

        # Initialize IT Support Agent
        support_agent = ITSupportAgent()

        # Build conversation history
        conversation_history = f"""
        Initial Issue: {ticket.description}
        Initial AI Response: {ticket.ai_response}
        Current Status: {ticket.status}
        """

        # Get agent's response with conversation history
        response, confidence, _ = support_agent.analyze_ticket(
            user_message,
            conversation_history=conversation_history
        )

        # Update ticket's confidence score and status
        if confidence < ticket.confidence_score:
            ticket.confidence_score = confidence
            if confidence < 0.7 and not ticket.requires_human_attention:
                ticket.requires_human_attention = True
                ticket.status = 'pending_review'
                notify_support_team(ticket)

        # Check if follow-up questions are needed
        needs_followup = support_agent.needs_followup(user_message)
        if needs_followup:
            response += "\n\nTo better assist you, could you please provide more details about:"
            if 'error message' in user_message.lower():
                response += "\n- The exact error message you're seeing"
            if 'not working' in user_message.lower():
                response += "\n- When did this issue start?"
                response += "\n- Have you made any recent changes to your system?"

        db.session.commit()
        return jsonify({'response': response})

    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/escalate_ticket', methods=['POST'])
def escalate_ticket():
    try:
        data = request.get_json()
        ticket_id = data.get('ticket_id')

        if not ticket_id:
            return jsonify({'error': 'Missing ticket ID'}), 400

        ticket = Ticket.query.get_or_404(ticket_id)
        ticket.requires_human_attention = True
        ticket.status = 'pending_review'
        db.session.commit()

        notify_support_team(ticket)
        return jsonify({'message': 'Ticket escalated successfully'})

    except Exception as e:
        logger.error(f"Error escalating ticket: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/resolve_ticket', methods=['POST'])
def resolve_ticket():
    try:
        data = request.get_json()
        ticket_id = data.get('ticket_id')

        if not ticket_id:
            return jsonify({'error': 'Missing ticket ID'}), 400

        ticket = Ticket.query.get_or_404(ticket_id)
        ticket.status = 'resolved'
        ticket.resolved_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'message': 'Ticket marked as resolved'})

    except Exception as e:
        logger.error(f"Error resolving ticket: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/dashboard')
def dashboard():
    try:
        # Get all filters from query params
        status_filter = request.args.get('status', 'all')
        category_filter = request.args.get('category', 'all')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Base query for tickets
        query = Ticket.query

        # Apply filters
        if status_filter != 'all':
            query = query.filter(Ticket.status == status_filter)

        if category_filter != 'all':
            query = query.filter(Ticket.category == category_filter)

        if start_date:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Ticket.created_at >= start_datetime)

        if end_date:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            # Add one day to include the entire end date
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            query = query.filter(Ticket.created_at <= end_datetime)

        # Get tickets ordered by creation date
        tickets = query.order_by(Ticket.created_at.desc()).all()

        # Calculate metrics using the same filtered query
        base_metrics_query = query
        metrics = {
            'total_tickets': query.count(),
            'resolved_tickets': query.filter(Ticket.status == 'resolved').count(),
            'pending_tickets': query.filter(Ticket.status == 'pending_review').count()
        }

        return render_template('dashboard.html', 
                             tickets=tickets, 
                             metrics=metrics,
                             status_filter=status_filter,
                             category_filter=category_filter,
                             start_date=start_date,
                             end_date=end_date,
                             now=datetime.utcnow())  # Add current time for age calculations
    except Exception as e:
        logger.error(f"Error accessing dashboard: {str(e)}")
        flash('Error accessing dashboard.', 'error')
        return redirect(url_for('index'))

@app.route('/download_csv')
def download_csv():
    try:
        # Use the same filtering logic as the dashboard
        status_filter = request.args.get('status', 'all')
        category_filter = request.args.get('category', 'all')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = Ticket.query

        if status_filter != 'all':
            query = query.filter(Ticket.status == status_filter)

        if category_filter != 'all':
            query = query.filter(Ticket.category == category_filter)

        if start_date:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Ticket.created_at >= start_datetime)

        if end_date:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            query = query.filter(Ticket.created_at <= end_datetime)

        tickets = query.order_by(Ticket.created_at.desc()).all()

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(['ID', 'Name', 'Email', 'Category', 'Status', 'Created At', 
                        'Resolved At', 'Updated At', 'Description', 'AI Response', 'Confidence Score'])

        # Write ticket data
        for ticket in tickets:
            writer.writerow([
                ticket.id,
                ticket.name,
                ticket.email,
                ticket.category,
                ticket.status,
                ticket.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                ticket.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.resolved_at else '',
                ticket.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                ticket.description,
                ticket.ai_response,
                ticket.confidence_score
            ])

        # Prepare the output
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'tickets_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )

    except Exception as e:
        logger.error(f"Error downloading CSV: {str(e)}")
        flash('Error downloading CSV file.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/chart_data')
def chart_data():
    try:
        # Calculate current time for age calculations
        now = datetime.utcnow()

        # Get all tickets
        tickets = Ticket.query.all()

        # Calculate age distribution
        age_bins = [0, 1, 2, 3, 7, 14, 30, float('inf')]  # in days
        age_labels = ['1 day', '2 days', '3 days', '1 week', '2 weeks', '1 month', '> 1 month']
        age_counts = [0] * len(age_labels)

        # Calculate resolution time trend (last 6 months)
        months = 6
        resolution_labels = []
        resolution_values = []

        for i in range(months-1, -1, -1):
            start_date = datetime.now() - timedelta(days=30 * (i+1))
            end_date = datetime.now() - timedelta(days=30 * i)
            month_tickets = Ticket.query.filter(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date,
                Ticket.resolved_at.isnot(None)
            ).all()

            if month_tickets:
                avg_resolution_time = sum(
                    (t.resolved_at - t.created_at).total_seconds() / 86400  # Convert to days
                    for t in month_tickets
                ) / len(month_tickets)
            else:
                avg_resolution_time = 0

            resolution_labels.append(start_date.strftime('%Y-%m'))
            resolution_values.append(round(avg_resolution_time, 1))

        # Calculate age distribution
        for ticket in tickets:
            end_time = ticket.resolved_at if ticket.resolved_at else now
            age_days = (end_time - ticket.created_at).total_seconds() / 86400  # Convert to days

            # Find appropriate bin
            for i, upper_bound in enumerate(age_bins[1:], 0):
                if age_days <= upper_bound:
                    age_counts[i] += 1
                    break

        return jsonify({
            'age_distribution': {
                'labels': age_labels,
                'values': age_counts
            },
            'resolution_time': {
                'labels': resolution_labels,
                'values': resolution_values
            }
        })

    except Exception as e:
        logger.error(f"Error generating chart data: {str(e)}")
        return jsonify({'error': 'Failed to generate chart data'}), 500

with app.app_context():
    db.create_all()