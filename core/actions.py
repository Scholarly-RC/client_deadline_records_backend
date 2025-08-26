from core.models import AppLog, Client, Notification, TaskApproval, TaskStatusHistory
from core.utils import get_admin_users, get_today_local


def create_log(user, details):
    """
    Create a new log entry in the application log.

    Args:
        user (User): The user associated with the log entry
        details (str): Description of the logged event
    """
    AppLog.objects.create(user=user, details=details)


def create_notifications(recipient, title, message, link):
    """
    Create a new notification for a user.

    Args:
        recipient (User): The user who will receive the notification
        title (str): Notification title/heading
        message (str): Detailed notification message
        link (str): URL link for the notification action
    """
    Notification.objects.create(
        recipient=recipient, title=title, message=message, link=link
    )


def send_notification_on_reminder_date():
    """
    Send notifications for deadlines where today is the reminder date.

    Creates notifications for all users who have deadlines with reminder dates
    matching today's date.
    """
    today = get_today_local()
    # for deadline in ClientDeadline.objects.filter(reminder_date=today):
    #     create_notifications(
    #         recipient=deadline.assigned_to,
    #         title="Upcoming Deadline Reminder",
    #         message=f"Friendly reminder: The deadline '{deadline}' is approaching. Please review your task.",
    #         link=f"/deadlines/{deadline.id}",
    #     )


def send_notification_for_due_tasks():
    """
    Send notifications for deadlines that are due today.

    Creates urgent notifications for all users who have deadlines with due dates
    matching today's date.
    """
    today = get_today_local()
    # for deadline in ClientDeadline.objects.filter(due_date=today):
    #     create_notifications(
    #         recipient=deadline.assigned_to,
    #         title="Action Required: Deadline Due Today",
    #         message=f"Urgent: The deadline '{deadline}' is due today. Please complete and submit as soon as possible.",
    #         link=f"/deadlines/{deadline.id}",
    #     )


def update_deadline_statuses():
    """Automatically update deadline statuses based on due dates and send notifications."""
    today = get_today_local()

    # pending_to_overdue = ClientDeadline.objects.filter(
    #     due_date__lt=today, status="pending"
    # ).select_related("assigned_to")

    # overdue_to_pending = ClientDeadline.objects.filter(
    #     due_date__gt=today, status="overdue"
    # ).select_related("assigned_to")

    # updates = []
    # for deadline in pending_to_overdue:
    #     deadline.status = "overdue"
    #     updates.append(deadline)

    # for deadline in overdue_to_pending:
    #     deadline.status = "pending"
    #     updates.append(deadline)

    # if updates:
    #     ClientDeadline.objects.bulk_update(updates, ["status"])

    #     # Send notifications
    #     for deadline in pending_to_overdue:
    #         create_notifications(
    #             recipient=deadline.assigned_to,
    #             title="Deadline Status Updated",
    #             message=f"The deadline '{deadline.title}' (due {deadline.due_date}) has been marked as Overdue.",
    #             link=f"/deadlines/{deadline.id}",
    #         )

    #     for deadline in overdue_to_pending:
    #         create_notifications(
    #             recipient=deadline.assigned_to,
    #             title="Deadline Status Updated",
    #             message=f"The deadline '{deadline.title}' (due {deadline.due_date}) has been reverted to Pending status.",
    #             link=f"/deadlines/{deadline.id}",
    #         )


def send_client_birthday_notifications():
    """
    Send birthday notifications to admin users for clients whose birthday is today.

    Checks all clients with birthdays matching today's date and sends notifications
    to all admin users to acknowledge or celebrate the client's birthday.
    The notification includes the client's name and a celebratory message.
    """
    today = get_today_local()
    for client in Client.objects.filter(date_of_birth=today):
        for admin in get_admin_users():
            create_notifications(
                recipient=admin,
                title=f"Client Birthday: {client.name}",
                message=f"Today is {client.name}'s birthday! Consider sending your wishes or acknowledging this special occasion.",
                link="",
            )


def initiate_task_approval(task, approvers_list, initiated_by):
    """
    Start the approval workflow for a task.

    Args:
        task (Task): The task to be approved
        approvers_list (list): List of User objects who will approve in sequence
        initiated_by (User): User who initiated the approval
    """
    from core.choices import TaskStatus

    # Clear any existing approval records for this task to prevent UNIQUE constraint violations
    # This allows re-initialization of approval workflows
    TaskApproval.objects.filter(task=task).delete()

    # Mark task as requiring approval and update status
    task.requires_approval = True
    task.current_approval_step = 1
    task.save(update_fields=["requires_approval", "current_approval_step"])

    # Add status update
    task.add_status_update(
        new_status=TaskStatus.FOR_CHECKING,
        remarks=f"Approval workflow initiated with {len(approvers_list)} approver(s): {', '.join([a.fullname for a in approvers_list])}",
        changed_by=initiated_by,
        change_type="approval",
    )

    # Create approval records for each step
    for step, approver in enumerate(approvers_list, 1):
        next_approver = approvers_list[step] if step < len(approvers_list) else None

        TaskApproval.objects.create(
            task=task,
            approver=approver,
            step_number=step,
            next_approver=next_approver,
            action="pending" if step == 1 else "pending",
        )

    # Set only first approval as active
    TaskApproval.objects.filter(task=task).exclude(step_number=1).update(
        action="pending"
    )

    # Log the action
    create_log(
        initiated_by,
        f"Initiated approval workflow for task: {task.description} with {len(approvers_list)} approver(s)",
    )

    # Notify first approver
    first_approver = approvers_list[0]
    create_notifications(
        recipient=first_approver,
        title="Task Approval Required",
        message=f"Task '{task.description}' for {task.client.name} requires your approval.",
        link=f"tasks/{task.id}/approve",
    )


def process_task_approval(task, approver, action, comments=None, next_approver=None):
    """
    Process an approval decision (approve, reject, or forward).

    Args:
        task (Task): The task being approved
        approver (User): User making the approval decision
        action (str): 'approved', 'rejected', or 'forwarded'
        comments (str): Optional comments from approver
        next_approver (User): If forwarding, the next approver
    """
    from core.choices import TaskStatus

    # Get current approval step
    current_approval = TaskApproval.objects.get(
        task=task, approver=approver, step_number=task.current_approval_step
    )

    if action == "rejected":
        # Update approval record
        current_approval.action = "rejected"
        current_approval.comments = comments
        current_approval.save()

        # Update task status with history
        task.requires_approval = False
        task.current_approval_step = 0
        task.save(update_fields=["requires_approval", "current_approval_step"])
        task.add_status_update(
            new_status=TaskStatus.FOR_REVISION,
            remarks=f"Rejected by {approver.fullname}: {comments}",
            changed_by=approver,
            change_type="approval",
            related_approval=current_approval,
        )

        # Notify original assignee
        create_notifications(
            recipient=task.assigned_to,
            title="Task Requires Revision",
            message=f"Your task '{task.description}' has been sent back for revision. Comments: {comments}",
            link=f"tasks/{task.id}",
        )

        create_log(approver, f"Rejected task approval: {task.description} - {comments}")

    elif action == "approved":
        # Update approval record
        current_approval.action = "approved"
        current_approval.comments = comments
        current_approval.save()

        # Check if there are more approval steps
        next_approval = TaskApproval.objects.filter(
            task=task, step_number=task.current_approval_step + 1
        ).first()

        if next_approval or next_approver:
            # Forward to next approver
            if next_approver:
                # Create new approval step if forwarding to someone not in original workflow
                new_step = task.current_approval_step + 1
                new_approval = TaskApproval.objects.create(
                    task=task,
                    approver=next_approver,
                    step_number=new_step,
                    action="pending",
                )
                task.current_approval_step = new_step
                task.save(update_fields=["current_approval_step"])
            else:
                # Move to next step in existing workflow
                task.current_approval_step += 1
                task.save(update_fields=["current_approval_step"])
                next_approval = TaskApproval.objects.get(
                    task=task, step_number=task.current_approval_step
                )
                next_approver = next_approval.approver
                new_approval = next_approval

            task.add_status_update(
                new_status=TaskStatus.FOR_CHECKING,
                remarks=f"Approved by {approver.fullname}, forwarded to {next_approver.fullname}. Comments: {comments or 'No comments'}",
                changed_by=approver,
                change_type="approval",
                related_approval=current_approval,
                force_history=True,  # Force history creation for intermediate approvals
            )

            # Notify next approver
            create_notifications(
                recipient=next_approver,
                title="Task Approval Required",
                message=f"Task '{task.description}' for {task.client.name} has been forwarded to you for approval by {approver.fullname}.",
                link=f"tasks/{task.id}/approve",
            )

            create_log(
                approver,
                f"Approved and forwarded task: {task.description} to {next_approver.fullname}",
            )

        else:
            # Final approval - mark task as completed
            task.requires_approval = False
            task.current_approval_step = 0
            task.completion_date = get_today_local()
            task.save(
                update_fields=[
                    "requires_approval",
                    "current_approval_step",
                    "completion_date",
                ]
            )
            task.add_status_update(
                new_status=TaskStatus.COMPLETED,
                remarks=f"Approved and completed by {approver.fullname}. Comments: {comments or 'No comments'}",
                changed_by=approver,
                change_type="approval",
                related_approval=current_approval,
            )

            # Notify original assignee
            create_notifications(
                recipient=task.assigned_to,
                title="Task Approved & Completed",
                message=f"Your task '{task.description}' has been approved and marked as completed by {approver.fullname}.",
                link=f"tasks/{task.id}",
            )

            create_log(
                approver, f"Final approval completed for task: {task.description}"
            )
