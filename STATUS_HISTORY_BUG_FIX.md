# Status History Bug Fix

## Problem Description

The application was creating duplicate status history entries when the status wasn't actually changed. This occurred when users updated task details (like remarks) but kept the same status, resulting in status history entries where `old_status` and `new_status` were identical.

Example of the problematic behavior:
```json
{
    "old_status": "On Going",
    "new_status": "On Going", 
    "changed_by": "Aiko Lareina Sullivan Rosas",
    "remarks": "On Goong",
    "date": "Aug 26, 2025 at 01:00 PM",
    "change_type": "Manual Update"
}
```

## Root Cause

The bug was located in two places:

1. **`Task.add_status_update()` method** in `core/models.py` - Always created status history entries regardless of whether status changed
2. **`update_deadline` view method** in `core/views.py` - Called `add_status_update()` without checking if status changed

## Solution

### 1. Modified `Task.add_status_update()` method

Added a check to only create status history entries when the status actually changes:

```python
def add_status_update(self, new_status, remarks=None, changed_by=None, change_type="manual", related_approval=None):
    """Add a status change record to the history"""
    old_status = self.status
    
    # Only create status history entry if status actually changed
    if old_status != new_status:
        self.status = new_status
        self.last_update = get_now_local()

        # Create status history record
        TaskStatusHistory.objects.create(
            task=self,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            remarks=remarks,
            change_type=change_type,
            related_approval=related_approval,
        )

        self.save(update_fields=["status", "last_update"])
    else:
        # If status didn't change but we have remarks, update them
        if remarks and remarks.strip():
            self.remarks = remarks
            self.last_update = get_now_local()
            self.save(update_fields=["remarks", "last_update"])
```

### 2. Improved `update_deadline` view method

Removed redundant status assignment and let `add_status_update()` handle all the logic:

```python
@action(detail=True, methods=["POST"], url_path="update-deadline")
def update_deadline(self, request, pk=None):
    task = self.get_object()
    try:
        updated_status = request.data.get("status")
        updated_remarks = request.data.get("remarks")
        
        # Update task fields
        if updated_remarks:
            task.remarks = updated_remarks
            
        # Use add_status_update to handle both status and remarks updates
        # The method now has built-in logic to prevent unnecessary status history entries
        task.add_status_update(
            new_status=updated_status,
            remarks=updated_remarks,
            changed_by=request.user,
        )
        
        serializer = TaskListSerializer(task)
        return Response(data=serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            data={"message": f"Something went wrong. {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
```

## Benefits

1. **Eliminates duplicate entries**: No more status history records where old and new status are the same
2. **Preserves legitimate changes**: Actual status changes still create proper history entries
3. **Handles remarks updates**: When only remarks change (no status change), the task is still updated appropriately
4. **Maintains backward compatibility**: All existing code that calls `add_status_update()` will work correctly
5. **Performance improvement**: Reduces unnecessary database writes for status history

## Testing

Added comprehensive unit tests in `core/tests.py` to ensure:
- No status history entry is created when status doesn't change
- Status history entry is created when status changes
- Remarks are properly updated even without status changes
- Multiple status changes create correct history sequence

All tests pass, confirming the fix works as intended.

## Impact

This fix affects:
- Manual status updates through the API
- Approval workflow status changes (but these typically involve actual status changes)
- Any other code that calls the `add_status_update()` method

The fix is backward compatible and doesn't break any existing functionality.