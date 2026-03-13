from collections import defaultdict
import csv
import datetime
import time
import os
import emails
import logging
from dotenv import load_dotenv
from pyairtable.api import Api as AirtableApi
from rate_limiter.python.package_throttler import PackageThrottler


airtable_throttle = PackageThrottler((), max_operations_in_window=5, rate_limit_window=1).execute_with_throttle

load_dotenv()

CSV_FILENAME = "coaching_report.csv"

def send_email(to_email: str, items, map, attachment=False, cc_emails=[], bcc_emails=[]) -> None:
    def getDateRange():
        today = datetime.date.today()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        prev_monday = start_of_week - datetime.timedelta(days=7)
        prev_sunday = start_of_week - datetime.timedelta(days=1)
        return f"{prev_monday.strftime('%b %d, %Y')} - {prev_sunday.strftime('%b %d, %Y')}"
    
    def mapName(id):
        return map.get(id, '')['name'] if map.get(id, '') else "*Employee Not Found*"
    
    from_name = os.getenv("EMAIL_FROM_NAME")
    from_addr = os.getenv("EMAIL_FROM")

    director_id = next(iter(items), None)
    director_tree = items.get(director_id, {}) if director_id else {}

    table_rows = ""

    def build_rows(manager_tree, level=0):
        nonlocal table_rows
        for manager_id, node in manager_tree.items():
            if manager_id == 'data':
                continue

            if not isinstance(node, dict):
                continue

            node_data = node.get('data')
            if node_data:
                indent_px = level * 24
                table_rows += f"""
                    <tr>
                        <td style="width:auto; white-space:nowrap; border:1px solid #ddd; padding:8px; padding-left:{8 + indent_px}px;">{mapName(manager_id)}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{node_data.get('num_of_employees', 0)}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{node_data.get('coaching_logs', 0)}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{node_data.get('compliance_percentage', 0):.0f}%</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{node_data.get('notes', '')}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{node_data.get('status', '')}</td>
                    </tr>
                """

            child_nodes = {k: v for k, v in node.items() if k != 'data'}
            if child_nodes:
                build_rows(child_nodes, level + 1)

    build_rows(director_tree)

    html_body = f"""
    <html>
    <body>
        <p>Hello {mapName(director_id)}!</p>
        <p>Please see below the Weekly Coaching Compliance Report for your Husk.</p>
        <h2>Coaching Compliance Report</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #4CAF50; color: white;">
                <th style="border: 1px solid #ddd; padding: 8px;">Manager</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Direct Reports</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Coaching Logs</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Compliance %</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Notes</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Status</th>
            </tr>
            {table_rows}
        </table>
        <p>This automated report is sent every Monday to help you track coaching activity and ensure all \n manager remain compliant.</p>
        <p>if you have any questions or need adjustments to the report, please let us know.</p>
        <p>Thank you!</p>
    </body>
    </html>
    """

    attempts = 0
    max_attempts = 2
    while attempts < max_attempts:
        try:
            message = emails.html(
                subject=f"Weekly Coaching Compliance Report ({getDateRange()})",
                html=html_body,
                text="Please view this email in an HTML-compatible email client.",
                mail_from=(from_name, from_addr),
                cc=cc_emails,
                bcc=bcc_emails,
            )
            today = datetime.date.today()
            week_num = today.isocalendar()[1]
            fileName = CSV_FILENAME.replace(".csv", f'_week{week_num}.csv')
            if attachment:
                with open(CSV_FILENAME, "rb") as f: 
                    message.attach( filename=fileName, data=f.read(), mime_type="text/csv" ) #W10_coaching_compliance_report.csv

            response = message.send(
                to=to_email,
                smtp={
                    "host": "smtp.gmail.com",
                    "port": 465,
                    "user": os.getenv("GMAIL_ADDRESS"),
                    "password": os.getenv("GMAIL_APP_PASSWORD"),
                    "ssl": True
                }
            )
            break
        except Exception as e:
            attempts += 1
            logging.error(f"Exception occurred while sending email to {to_email}: {e} \n\tAttempt {attempts} of {max_attempts}")
            time.sleep(2)
    
    if response.status_code == 250:
        print(f"Email sent to {to_email} successfully.")
    else:
        logging.error(f"Failed to send email to {to_email}. "
                      f"SMTP status={response.status_code}")
        
def get_table(tab, view):
    x = 0
    while x <= 2:
        try:
            airtable = AirtableApi(os.getenv("AIRTABLE_API_KEY"))
            table = airtable.table("appfccXiah8EtMfbZ", tab)
            records = airtable_throttle(table, 'all', view=view)
            return records
        except Exception as e:
            x += 1
            logging.error(f"Attempt {x} failed: {e}")

    logging.error("Failed to retrieve Airtable records after 2 attempts")
    return None

def getDirectory(workers):
    directory = []
    for record in workers:
        fields = record.get('fields', {})
        director_id = fields.get('Brand Director')
        manager_id = fields.get('Manager') if fields.get('Manager') else director_id
        employee_id = record.get('id')
        project_manager_id = fields.get('Project Manager') if fields.get('Project Manager') else None
        if director_id and fields.get('Worker') != 'Steven Pope':
            directory.append({
                "employee_id": employee_id,
                "project_manager_id": project_manager_id[0] if project_manager_id else None,
                "manager_id": manager_id[0],
                "director_id": director_id[0]
            })
    return directory

def getCoacingDirectory(coaching_calls):
    directory = []
    for record in coaching_calls:
        fields = record.get('fields', {})
        coach_id = fields.get('Coach')
        trainee_id = fields.get('Trainee')
        directory.append({
            "coach_id": coach_id[0] if coach_id else None,
            "trainee_id": trainee_id[0] if trainee_id else None,
        })
    return directory

def build_tree(data, top_manager):
    tree = defaultdict(list)

    for worker, project_manager, manager, director in data:
        worker = worker.strip()
        # Decide parent based on presence of project_manager
        if project_manager and project_manager.strip():
            parent = project_manager.strip()
        elif manager and manager.strip():
            parent = manager.strip()
        else:
            parent = director.strip()

        tree[parent].append(worker)

    def build_dict(manager):
        return {
            employee: build_dict(employee)
            for employee in tree.get(manager, [])
        }

    return {top_manager: build_dict(top_manager)}

def find_managers(tree):
    managers = []

    for person, reports in tree.items():
        if reports:  # if dictionary not empty
            managers.append(person)
            managers.extend(find_managers(reports))  # check deeper levels

    return managers

def prune_tree(tree):
    if not isinstance(tree, dict):
        return tree

    cleaned = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            pruned = prune_tree(value)
            # keep the branch if it has children
            if pruned:
                cleaned[key] = pruned
        else:
            cleaned[key] = value
    return cleaned

def add_key(tree, target, new_key, new_value):
    """Find target key in nested dict and add a new key/value under it."""
    if target in tree:
        if isinstance(tree[target], dict):
            tree[target][new_key] = new_value
        return True
    for k, v in tree.items():
        if isinstance(v, dict):
            if add_key(v, target, new_key, new_value):
                return True
    return False

def main(dev_mode=False):
    print(f"Running in {'development' if dev_mode else 'production'} mode")

    workers = get_table("Workers", "Active Workers")
    name_map = {worker['id']: {'name': worker['fields'].get('Worker'), 'email': worker['fields'].get('Work Email Address copy')} for worker in workers}
    directory = getDirectory(workers)

    coaching_calls = get_table('tblA4AbLZQcdgi0RC', 'viwdYEfy7lkI2XCsr')
    coaching_directory = getCoacingDirectory(coaching_calls)

    email_data = []
    directors = set([director['director_id'] for director in directory])
    for director in directors:
        list_sub_items = []
        managers = set([item['manager_id'] for item in directory if item['director_id'] == director])
        attachment = []
        
        #get the employees with manager == director
        all_employees = [(item['employee_id'], item['project_manager_id'], item['manager_id'], item['director_id']) for item in directory if item['director_id'] == director]
        department = build_tree(all_employees, director)
        managers = find_managers(department)

        for manager in managers:
            if manager == director: continue
            employees = []
            for e in all_employees:
                manager_id = e[2]
                project_manager_id = e[1]
                employee_id = e[0]

                if employee_id == manager or employee_id == project_manager_id: 
                    continue
            
                if manager_id == manager and project_manager_id == None: 
                    employees.append(employee_id)
                if project_manager_id == manager:
                    employees.append(employee_id)

            tranings_done = 0
            for employee in employees:
                coaching_logs = [log for log in coaching_directory if log['coach_id'] == manager and log['trainee_id'] == employee]
                
                logs = [{
                    "Manager": name_map[manager]['name'] if name_map.get(manager) else "Unknown Manager",
                    "Employee": name_map[employee]['name'] if name_map.get(employee) else "Unknown Employee",
                    "Coached": "Yes" if coaching_logs else "No"
                }]
                attachment.extend(logs)

                if coaching_logs:
                        tranings_done += 1
                        
            percentage = (tranings_done/len(employees))*100 if len(employees) > 0 else 0
            add_key(department, manager, "data", {
                "num_of_employees": len(employees),
                "coaching_logs": tranings_done,
                "compliance_percentage": percentage,
                "notes":  f"Follow-up required"if percentage < 85 else f"{len(employees) - tranings_done} Pending",
                "status": "⚠️" if percentage <= 84 and percentage >=75 else "❌" if percentage < 75 else "✅"
            })

        department_logs = prune_tree(department)
        email_data.append({
            "data": department_logs, 
            "attachment": attachment
        })

    
    for item in email_data:
        if item.get('data', {}) == {}: continue

        director_email = name_map[item['director_id']]['email'] if not dev_mode else os.getenv("TEST_EMAIL")

        #log for file attachment
        if item['attachment']:
            with open(CSV_FILENAME, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=item['attachment'][0].keys()) 
                writer.writeheader() 
                writer.writerows(item['attachment'])

        cc_emails = [email for email in os.getenv("CC_EMAILS", "").split(",") if email.strip()] if dev_mode else []
        bcc_emails = [email for email in os.getenv("BCC_EMAILS", "").split(",") if email.strip()] if dev_mode else []
        send_email(to_email=director_email, cc_emails=cc_emails, bcc_emails=bcc_emails, items=item.get('data', {}), map=name_map, attachment= bool(item['attachment']))


if __name__ == "__main__":
    dev_mode = os.getenv("DEV_MODE", "False").lower() == "true"

    print(" --------------- Starting execution")
    main(dev_mode=dev_mode)
    print(" --------------- Finished execution")