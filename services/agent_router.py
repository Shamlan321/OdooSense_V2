#!/usr/bin/env python3
"""
Agent Router
===========
Intelligently routes queries to appropriate agents:
- Main Agent: Shortcuts, docs, dynamic records, document processing
- Reporting Agent: CRUD operations, reports, charts, PDFs
"""

import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class AgentRouter:
    """
    Routes queries to appropriate agents based on keywords and intent.
    Maintains separation between main agent and reporting agent functionality.
    """
    
    def __init__(self):
        # Reporting agent keywords - these trigger the reporting agent
        self.reporting_keywords = [
            # Report generation
            "generate report", "create report", "export report", "pdf report",
            "sales report", "inventory report", "financial report", "customer report",
            "employee report", "product report", "invoice report", "purchase report",
            
            # Charts and graphs
            "create chart", "generate chart", "create graph", "generate graph",
            "plot data", "visualize", "chart", "graph", "plot",
            
            # CRUD operations
            "create record", "update record", "delete record", "modify record",
            "add new", "edit", "remove", "insert", "update", "delete",
            
            # Data operations
            "export to pdf", "export to excel", "export data", "download report",
            "generate pdf", "create pdf", "save as pdf", "export as",
            
            # Specific report types
            "monthly report", "quarterly report", "annual report", "daily report",
            "summary report", "detailed report", "analytics report", "dashboard",
            
            # Data analysis
            "analyze data", "data analysis", "statistics", "metrics", "kpi",
            "performance report", "trend analysis", "comparison report"
        ]
        
        # Main agent keywords - these stay with the main agent
        self.main_keywords = [
            # Navigation and shortcuts
            "shortcut", "navigate", "go to", "open", "access", "menu",
            "where is", "how to access", "show me", "take me to",
            
            # Documentation and help
            "help", "assist", "guide", "documentation", "manual", "tutorial",
            "how to", "what is", "explain", "describe",
            
            # Document processing
            "document", "file", "upload", "process document", "extract",
            "invoice", "receipt", "contact", "lead", "linkedin",
            
            # General queries
            "what", "how", "when", "where", "why", "tell me", "show me",
            "find", "search", "look for", "get", "fetch",
            
            # Email and communication
            "email", "mail", "message", "communication", "inbox",
            
            # General assistance
            "assist", "help", "support", "guide", "advise"
        ]
        
        # High-priority reporting patterns (these override main agent)
        self.reporting_patterns = [
            r"generate.*report",
            r"create.*report", 
            r"export.*pdf",
            r"create.*chart",
            r"generate.*graph",
            r"plot.*data",
            r"analyze.*data",
            r"create.*record",
            r"update.*record",
            r"delete.*record",
            r"monthly.*report",
            r"quarterly.*report",
            r"annual.*report",
            r"sales.*report",
            r"inventory.*report",
            r"financial.*report"
        ]
        
        # High-priority main agent patterns
        self.main_patterns = [
            r"navigate.*to",
            r"go.*to",
            r"where.*is",
            r"how.*to.*access",
            r"shortcut.*for",
            r"process.*document",
            r"upload.*file",
            r"extract.*from",
            r"help.*with",
            r"assist.*with"
        ]
    
    def route_query(self, message: str, session_id: str = None) -> str:
        """
        Determine which agent should handle the query
        
        Args:
            message: User's query message
            session_id: Session identifier (for logging)
            
        Returns:
            str: "reporting_agent" or "main_agent"
        """
        try:
            message_lower = message.lower().strip()
            
            # Check for explicit agent selection
            if "reporting agent" in message_lower or "report agent" in message_lower:
                logger.info(f"Session {session_id}: Explicit routing to reporting agent")
                return "reporting_agent"
            
            if "main agent" in message_lower or "general agent" in message_lower:
                logger.info(f"Session {session_id}: Explicit routing to main agent")
                return "main_agent"
            
            # Check high-priority patterns first
            for pattern in self.reporting_patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    logger.info(f"Session {session_id}: Pattern '{pattern}' matched - routing to reporting agent")
                    return "reporting_agent"
            
            for pattern in self.main_patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    logger.info(f"Session {session_id}: Pattern '{pattern}' matched - routing to main agent")
                    return "main_agent"
            
            # Check keyword matches
            reporting_score = sum(1 for keyword in self.reporting_keywords 
                                if keyword in message_lower)
            main_score = sum(1 for keyword in self.main_keywords 
                           if keyword in message_lower)
            
            # If both have matches, use the higher score
            if reporting_score > 0 and main_score > 0:
                if reporting_score >= main_score:
                    logger.info(f"Session {session_id}: Reporting score ({reporting_score}) >= Main score ({main_score}) - routing to reporting agent")
                    return "reporting_agent"
                else:
                    logger.info(f"Session {session_id}: Main score ({main_score}) > Reporting score ({reporting_score}) - routing to main agent")
                    return "main_agent"
            
            # If only one has matches, use that
            if reporting_score > 0:
                logger.info(f"Session {session_id}: Reporting keywords found - routing to reporting agent")
                return "reporting_agent"
            
            if main_score > 0:
                logger.info(f"Session {session_id}: Main keywords found - routing to main agent")
                return "main_agent"
            
            # Default to main agent for ambiguous queries
            logger.info(f"Session {session_id}: No clear pattern - defaulting to main agent")
            return "main_agent"
            
        except Exception as e:
            logger.error(f"Error in query routing: {str(e)}")
            # Default to main agent on error
            return "main_agent"
    
    def get_routing_info(self, message: str) -> Dict[str, Any]:
        """
        Get detailed routing information for debugging
        
        Args:
            message: User's query message
            
        Returns:
            Dict containing routing analysis
        """
        message_lower = message.lower().strip()
        
        # Find matching keywords
        reporting_matches = [kw for kw in self.reporting_keywords if kw in message_lower]
        main_matches = [kw for kw in self.main_keywords if kw in message_lower]
        
        # Find matching patterns
        reporting_pattern_matches = []
        main_pattern_matches = []
        
        for pattern in self.reporting_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                reporting_pattern_matches.append(pattern)
        
        for pattern in self.main_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                main_pattern_matches.append(pattern)
        
        # Calculate scores
        reporting_score = len(reporting_matches) + len(reporting_pattern_matches)
        main_score = len(main_matches) + len(main_pattern_matches)
        
        # Determine final route
        final_route = self.route_query(message)
        
        return {
            "message": message,
            "final_route": final_route,
            "reporting_score": reporting_score,
            "main_score": main_score,
            "reporting_keywords": reporting_matches,
            "main_keywords": main_matches,
            "reporting_patterns": reporting_pattern_matches,
            "main_patterns": main_pattern_matches,
            "reasoning": {
                "reporting_score": reporting_score,
                "main_score": main_score,
                "decision": f"Chose {final_route} based on scores"
            }
        }
    
    def add_custom_keywords(self, agent_type: str, keywords: List[str]):
        """
        Add custom keywords for routing
        
        Args:
            agent_type: "reporting_agent" or "main_agent"
            keywords: List of keywords to add
        """
        if agent_type == "reporting_agent":
            self.reporting_keywords.extend(keywords)
        elif agent_type == "main_agent":
            self.main_keywords.extend(keywords)
        else:
            logger.error(f"Invalid agent type: {agent_type}")
    
    def add_custom_patterns(self, agent_type: str, patterns: List[str]):
        """
        Add custom regex patterns for routing
        
        Args:
            agent_type: "reporting_agent" or "main_agent"
            patterns: List of regex patterns to add
        """
        if agent_type == "reporting_agent":
            self.reporting_patterns.extend(patterns)
        elif agent_type == "main_agent":
            self.main_patterns.extend(patterns)
        else:
            logger.error(f"Invalid agent type: {agent_type}")

# Global router instance
agent_router = AgentRouter() 