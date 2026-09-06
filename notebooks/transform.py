# notebooks/transform.py — Spark Ingest + Transform Job
# Task 1 of Databricks Ingest Job
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf, explode, to_timestamp, lit, when, concat_ws, collect_list
from pyspark.sql.types import ArrayType, StringType

spark = SparkSession.builder.getOrCreate()

# Reads the real Volume path Section 4.5 uploads to
raw_checkpoints_df = spark.read.json(
    "/Volumes/checkpoint_dx/checkpoints/raw_exports/checkpoints_export.json",
    multiLine=True,
)

# Convert string timestamp to TimestampType matching table DDL
checkpoints_with_ts = raw_checkpoints_df.withColumn(
    "timestamp_parsed",
    to_timestamp(col("timestamp")).cast("timestamp")
)

normalized_df = (checkpoints_with_ts
    .select(col("checkpoint_id"), col("session_id"), col("branch"), col("prompt_text"),
            col("file_changes"), col("agent_name"), col("model_name"),
            col("timestamp_parsed").alias("timestamp"))
    .dropDuplicates(["checkpoint_id"]))
normalized_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("checkpoint_dx.checkpoints.checkpoints_normalized")

branch_summary_df = normalized_df.groupBy("branch", "agent_name").count().withColumnRenamed("count", "checkpoint_count")
branch_summary_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("checkpoint_dx.checkpoints.branch_agent_summary")

def segment_prompt(prompt_text: str):
    import re
    if not prompt_text:
        return []
    return [s for s in re.split(r'(?<=[.!?])\s+', prompt_text.strip()) if len(s.split()) > 2]
segment_prompt_udf = udf(segment_prompt, ArrayType(StringType()))

prompt_clauses = (normalized_df
    .withColumn("clauses", segment_prompt_udf(col("prompt_text")))
    .withColumn("clause", explode(col("clauses")))
    .select("checkpoint_id", "session_id", "clause"))
prompt_clauses.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("checkpoint_dx.checkpoints.prompt_clauses")

requirement_keywords = ["add", "implement", "fix", "ensure", "must", "should", "create"]
is_requirement_udf = udf(lambda c: any(k in c.lower() for k in requirement_keywords), "boolean")
requirements_df = (prompt_clauses
    .withColumn("is_requirement", is_requirement_udf(col("clause")))
    .filter(col("is_requirement"))
    .selectExpr(
        "checkpoint_id", "session_id", "clause as requirement_text",
        "'not_started' as status",
        "current_timestamp() as created_at",
    ))
requirements_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("checkpoint_dx.checkpoints.requirements")

deadend_phrases = ["let me try", "that didn't work", "instead", "abandon", "revert", "different approach", "race condition"]
flag_deadend_udf = udf(lambda t: bool(t) and any(p in t.lower() for p in deadend_phrases), "boolean")
deadend_candidates_df = (checkpoints_with_ts
    .withColumn("has_deadend_signal", flag_deadend_udf(col("transcript")))
    .filter(col("has_deadend_signal"))
    .select("checkpoint_id", "session_id", col("timestamp_parsed").alias("timestamp"), "transcript", "agent_name", "model_name"))
deadend_candidates_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("checkpoint_dx.checkpoints.deadend_candidates")

exploded_changes = (normalized_df
    .withColumn("change", explode(col("file_changes")))
    .select("checkpoint_id", col("change.file_path").alias("file_path"), col("change.diff_hunk").alias("diff_hunk")))

# Combine all diff hunks per checkpoint for robust lexical conformance
checkpoint_hunks = (exploded_changes
    .groupBy("checkpoint_id")
    .agg(concat_ws(" ", collect_list("diff_hunk")).alias("all_hunks")))

def check_conformance(clause: str, hunks: str) -> str:
    """MVP lexical-overlap substitute for semantic alignment."""
    if not clause or not hunks:
        return "gap"
    clause_words = {w.lower() for w in clause.split() if len(w) > 3}
    hunk_words = {w.lower() for w in hunks.split() if len(w) > 3}
    return "met" if bool(clause_words & hunk_words) else "gap"

conformance_udf = udf(check_conformance, StringType())

intent_conformance_df = (prompt_clauses.alias("c")
    .join(checkpoint_hunks.alias("h"), col("c.checkpoint_id") == col("h.checkpoint_id"), "left")
    .withColumn("implementation_status", conformance_udf(col("c.clause"), col("h.all_hunks")))
    .withColumn("confidence_score", when(col("implementation_status") == "met", 0.9).otherwise(0.5))
    .select(col("c.checkpoint_id").alias("checkpoint_id"), col("c.clause").alias("clause"),
            col("implementation_status"), col("confidence_score")))

intent_conformance_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("checkpoint_dx.checkpoints.intent_conformance")

print("Transform complete: checkpoints_normalized, requirements, deadend_candidates, intent_conformance tables written.")
