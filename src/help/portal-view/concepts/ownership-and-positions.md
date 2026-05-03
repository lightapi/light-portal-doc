# Ownership And Positions

Portal records can have an individual owner and a position owner.

`owner_user_id` is derived from the authenticated user when a record is created.
It should not be submitted from normal browser forms.

`owner_position_id` is optional and can be selected on owner-aware forms. It
allows users with the matching effective position to see or manage the record
when service-side authorization grants that scope.

Rows with no owner user and no owner position are legacy or unassigned records.
They should normally be visible only to all-scope administrators until ownership
is assigned.

