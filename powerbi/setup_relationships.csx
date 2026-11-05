// Align the imported Power BI relationships with the documented star schema.
// TOM stores many-to-one relationships from fact (FromColumn) to dimension
// (ToColumn), even though the report design is described dimension -> fact.

var serviceFact = Model.Tables["fact_service_type_interval"];
var serviceDimension = Model.Tables["dim_service_type"];
var queueDimension = Model.Tables["dim_queue"];

// Remove the snowflake relationship automatically inferred by Power BI.
var inferredSnowflake = Model.Relationships
    .Where(relationship =>
        relationship.FromColumn == serviceDimension.Columns["queue_id"] &&
        relationship.ToColumn == queueDimension.Columns["queue_id"])
    .ToList();
foreach (var relationship in inferredSnowflake)
{
    relationship.Delete();
}

Action<TabularEditor.TOMWrapper.Column, TabularEditor.TOMWrapper.Column> ensureRelationship =
    (fromColumn, toColumn) =>
    {
        var exists = Model.Relationships.Any(relationship =>
            relationship.FromColumn == fromColumn &&
            relationship.ToColumn == toColumn
        );
        if (!exists)
        {
            var relationship = Model.AddRelationship();
            relationship.FromColumn = fromColumn;
            relationship.ToColumn = toColumn;
        }
    };

ensureRelationship(
    serviceFact.Columns["queue_id"],
    queueDimension.Columns["queue_id"]
);
ensureRelationship(
    serviceFact.Columns["service_type_code"],
    serviceDimension.Columns["service_type_code"]
);

Model.SetAnnotation("CALL_CENTER_WFM_RELATIONSHIPS_VERSION", "1.0.0");
Info("Call Center WFM service-type relationships aligned to star schema.");
