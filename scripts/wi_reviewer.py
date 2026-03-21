import asyncio
import sys
import os
from datetime import datetime
from notebooklm import NotebookLMClient
from logger_utils import get_logger, LogDest
from reviewer_ai import generate_next_query

async def main():
    """Main function to perform 3GPP recursive analysis using NotebookLM."""
    recursive_deep = 5
    # Initialize the logger instance once
    log = get_logger("wi_reviewer.py")
    
    log.info("Starting 3GPP Recursive Analysis Script", dest=LogDest.BOTH)
    log.debug("Logger initialized successfully", dest=LogDest.FILE)
    
    try:
        # 1. Connects to the session created by 'notebooklm login'
        log.info("Connecting to NotebookLM client...", dest=LogDest.BOTH)
        async with await NotebookLMClient.from_storage() as client:
            log.info("Successfully connected to NotebookLM client", dest=LogDest.BOTH)
            
            # PASTE YOUR ID HERE (from the browser URL)
            notebook_id = "1c89a85d-945a-4667-8d0b-336eefc1e46a"
            log.info(f"Using notebook ID: {notebook_id}", dest=LogDest.FILE)
            
            # Initial query for 3GPP analysis
            current_query = """Role: 
You are a Senior 3GPP Standards Delegate and Lead Rapporteur for RAN1/RAN2. 
Your goal is to conduct a forensic technical audit of the provided documents regarding Rel-18 Coverage Enhancement for NR NTN.
Task: Identify, categorize, and track every technical bottleneck and "problem statement" shared across the contribution set. For each problem identified, you must provide:
Technical Definition: What is the specific physical layer or protocol-level issue? (e.g., Phase discontinuity during TA pre-compensation).
The "Why": Explain the physics or logic that makes this a problem. Why can’t legacy NR (Terrestrial) mechanisms solve it? (e.g., Satellite velocity vs. UE oscillator drift).
Use Case/Scenario: Cite the specific baseline parameters (e.g., LEO-1200, S-band, -5.5 dBi antenna gain, 3dB polarization loss).
Discussion Roadmap (The 3GPP Trail): Track the problem through the meeting timeline.
Where was it first observed?
How did the consensus change from RAN1#109-e to RAN1#116?
Identify "Working Assumptions" (WA) that were later superseded.
Traceability: You MUST cite the exact TDoc (e.g., R1-2203159 or R1-2309392) and the specific "Observation" or "Proposal" number.
Priority Areas of Analysis:
PUCCH Repetition for Msg4 HARQ-ACK: Analyze the debate between "Repetition Request" vs. "Capability Report" and the capacity bottleneck of the 16 common PUCCH resources (R1-2311637).
DMRS Bundling & Phase Continuity: Analyze how TA pre-compensation updates at the UE side break the bundling window (R1-2208834).
The RSRP Threshold Logic: Why is a simple RSRP threshold problematic in NTN compared to TN? (Include the "Satellite Movement" and "Elevation Angle" arguments from R2-2212240).
Polarization Mismatch: Review the 3dB loss assumption and why circular-to-linear polarization creates a coverage hole for smartphones (R1-2203159).
Formatting Instructions:
Present findings in a "Problem-to-Solution Evolution Table."
Column 1: Problem ID & Reference.
Column 2: Technical Root Cause.
Column 3: Meeting Evolution (RAN1#110 -> #114bis).
Column 4: Final Rel-18 Status (Agreed/Maintenance/Open).
Constraint: Do not summarize general concepts. Focus on the conflicts between company contributions (e.g., Huawei vs. Ericsson vs. Qualcomm) and how they were resolved in the Moderator Summaries.
Maintain a technical, "Specification-style" tone."""

            final_document = "# 3GPP Recursive Analysis Report\n"
            log.info("Starting analysis with {recursive_deep} refinement stages", dest=LogDest.BOTH)

            for i in range(recursive_deep):  # Set this to however many refinements you want
                log.info(f"Starting Analysis Stage {i+1}/{recursive_deep}", dest=LogDest.BOTH)
                
                try:
                    # 2. Sends the query to the NotebookLM AI
                    log.debug(f"Sending query to NotebookLM (Stage {i+1})", dest=LogDest.FILE)
                    log.debug(f"Query {i+1} : {current_query}", dest=LogDest.FILE)
                    result = await client.chat.ask(notebook_id, current_query)
                    response_text = result.answer                    
                    log.debug(f"Received response from NotebookLM (Stage {i+1})", dest=LogDest.FILE)
                    
                    # Append the response to your running document
                    final_document += f"\n\n## Analysis Stage {i+1}\n{response_text}"
                    log.debug(f"Response {i+1} : {response_text}", dest=LogDest.FILE)
                    log.info(f"Completed Analysis Stage {i+1}/{recursive_deep}", dest=LogDest.BOTH)
                    
                    current_query = generate_next_query(response_text)
                    log.debug(f"Generated new query for Stage {i+2} (if applicable)", dest=LogDest.FILE)
                 
                    await asyncio.sleep(30)
                        
                except Exception as e:
                    log.error(f"Error in Analysis Stage {i+1}: {str(e)}", dest=LogDest.BOTH)
                    log.debug(f"Full error details: {repr(e)}", dest=LogDest.FILE)
                    # Continue with next iteration if possible
                    
            # 4. Final Export to Markdown
            output_dir = "/process/report"
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = "CoverageEnhancement_NR_NTN_enh"
            output_file = os.path.join(output_dir, f"{timestamp}_report_{base_name}.md")
            
            log.info(f"Saving final analysis to {output_file}", dest=LogDest.BOTH)
            
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(final_document)
                log.info(f"Successfully saved analysis to {output_file}", dest=LogDest.BOTH)
                log.debug(f"Final document length: {len(final_document)} characters", dest=LogDest.FILE)
                
            except Exception as e:
                log.error(f"Failed to save analysis file: {str(e)}", dest=LogDest.BOTH)
                log.debug(f"File save error details: {repr(e)}", dest=LogDest.FILE)
                raise
                
    except Exception as e:
        log.error(f"Critical error in main execution: {str(e)}", dest=LogDest.BOTH)
        log.debug(f"Full error traceback: {repr(e)}", dest=LogDest.FILE)
        sys.exit(1)
        
    log.info("3GPP Recursive Analysis Script completed successfully", dest=LogDest.BOTH)

if __name__ == "__main__":
    asyncio.run(main())