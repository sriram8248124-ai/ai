"""
Advanced Ticket System Dashboard
"""

import json
import os
from datetime import datetime
from enum import Enum

TICKETS_FILE = "tickets.json"

class TicketStatus(Enum):
    OPEN = "🔴 Open"
    IN_PROGRESS = "🟡 In Progress"
    RESOLVED = "🟢 Resolved"
    CLOSED = "⚫ Closed"

def load_tickets():
    """Load all tickets"""
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_tickets(tickets):
    """Save tickets"""
    with open(TICKETS_FILE, 'w') as f:
        json.dump(tickets, f, indent=2)

def create_ticket(guild_id, user_id, username, title, description, category="general"):
    """Create new ticket"""
    tickets = load_tickets()
    
    # Generate ticket ID
    ticket_id = f"TKT-{guild_id}-{len(tickets) + 1}"
    
    tickets[ticket_id] = {
        "id": ticket_id,
        "guild_id": guild_id,
        "user_id": user_id,
        "username": username,
        "title": title,
        "description": description,
        "category": category,
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "assigned_to": None,
        "channel_id": None,
    }
    
    save_tickets(tickets)
    return ticket_id, tickets[ticket_id]

def update_ticket_status(ticket_id, status):
    """Update ticket status"""
    tickets = load_tickets()
    if ticket_id in tickets:
        tickets[ticket_id]["status"] = status
        tickets[ticket_id]["updated_at"] = datetime.now().isoformat()
        save_tickets(tickets)
        return True
    return False

def close_ticket(ticket_id):
    """Close ticket"""
    return update_ticket_status(ticket_id, "closed")

def get_ticket(ticket_id):
    """Get ticket details"""
    tickets = load_tickets()
    return tickets.get(ticket_id)

def list_tickets(guild_id, status=None):
    """List tickets for guild"""
    tickets = load_tickets()
    guild_tickets = {k: v for k, v in tickets.items() if v["guild_id"] == guild_id}
    
    if status:
        guild_tickets = {k: v for k, v in guild_tickets.items() if v["status"] == status}
    
    return guild_tickets

TICKET_CATEGORIES = {
    "bug": "🐛 Bug Report",
    "feature": "✨ Feature Request",
    "support": "🆘 Support",
    "payment": "💳 Payment Issue",
    "other": "❓ Other",
}
