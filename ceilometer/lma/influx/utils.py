import datetime
from ceilometer.storage import models
from ceilometer import utils

MEASUREMENT = "ceilometer"

DEFAULT_AGGREGATES = ["mean", "sum", "count", "min", "max"]

TRANSITION = {
    "avg": "mean"
}

DETRANSITION = {
    "mean": "avg"
}

OP_SIGN = {'eq': '=', 'lt': '<', 'le': '<=', 'ne': '!=', 'gt': '>', 'ge': '>='}


def combine_filter_query(sample_filter, require_meter=False):
    expressions = []
    if sample_filter.user:
        expressions.append(("user_id", "=", sample_filter.user))
    if sample_filter.project:
        expressions.append(("project_id", "=", sample_filter.project))
    if sample_filter.meter:
        expressions.append(("meter", "=", sample_filter.meter))
    elif require_meter:
        raise RuntimeError('Missing required meter specifier')

    start_op = sample_filter.start_timestamp_op or ">"

    if sample_filter.start_timestamp:
        expressions.append(("time",
                            OP_SIGN.get(start_op, start_op),
                            sample_filter.start_timestamp))

    end_op = sample_filter.end_timestamp_op or "<"
    if sample_filter.end_timestamp:
        expressions.append(("time",
                            OP_SIGN.get(end_op, end_op),
                            sample_filter.end_timestamp))

    if sample_filter.resource:
        expressions.append(("resource_id", "=", sample_filter.resource))
    if sample_filter.source:
        expressions.append(("source", "=", sample_filter.source))
    if sample_filter.message_id:
        expressions.append(("message_id", "=", sample_filter.message_id))

    if sample_filter.metaquery:
        for field, value in sample_filter.metaquery.items():
            expressions.append((field, "=", value))

    query = " and ".join(("%s%s'%s'" % exp for exp in expressions))

    return query


def combine_groupby(period, groupby):
    return ", ".join((groupby or []) +
                     (["time({period}s)".format(period=period)]
                      if period > 0 else []))


def combine_aggregation(aggregate):
    aggregates = []

    if not aggregate:
        for func in DEFAULT_AGGREGATES:
            aggregates.append("{func}(value) as {func}".format(func=func))
    else:
        for func in aggregate:
            aggregates.append("{func}(value) as {func}".format(
                func=TRANSITION.get(func, func)))

    return ", ".join(aggregates + combine_duration_aggregates())


def combine_duration_aggregates():
    duration_aggregates = ["{func}(timestamp) as {func}".format(func=func)
                           for func in ("last", "first")]
    return duration_aggregates


def combine_aggregate_query(sample_filter, period, groupby, aggregate):
    query = ("SELECT {select} FROM {measurement} WHERE {where} ".format(
        select=combine_aggregation(aggregate),
        where=combine_filter_query(sample_filter), measurement=MEASUREMENT
    ))
    groupby = combine_groupby(period, groupby)
    if groupby:
        query += "GROUP BY {groupby} fill(none)".format(groupby=groupby)
    return query


def combine_time_bounds_query(sample_filter):
    return "SELECT {select} from {measurement} WHERE {where}".format(
        select=",".join(combine_duration_aggregates()),
        where=combine_filter_query(sample_filter),
        measurement=MEASUREMENT
    )


def combine_list_query(sample_filter, limit):
    where = combine_filter_query(sample_filter)
    return ("SELECT * FROM {measurement} WHERE {where} LIMIT {limit}".format(
        measurement=MEASUREMENT,
        where=where,
        limit=limit
    ))


def point_to_stat(point, tags, period, aggregate):
    kwargs = {}
    if not aggregate:
        for func in DEFAULT_AGGREGATES:
            kwargs[DETRANSITION.get(func, func)] = point.get(func)
    else:
        kwargs['aggregate'] = {}
        for func in aggregate:
            kwargs['aggregate'][func] = point.get(TRANSITION.get(func, func))

    kwargs["groupby"] = tags
    kwargs["duration_start"] = utils.sanitize_timestamp(point["first"])
    kwargs["duration_end"] = utils.sanitize_timestamp(point["last"])
    kwargs["duration"] = (kwargs["duration_end"] -
                          kwargs["duration_start"]).total_seconds()
    kwargs["period"] = period
    kwargs["period_start"] = utils.sanitize_timestamp(point["time"])
    kwargs["period_end"] = (utils.sanitize_timestamp(point["time"]) +
                            datetime.timedelta(seconds=period or 0))
    kwargs["unit"] = "%"
    return models.Statistics(**kwargs)


def transform_metadata(point):
    metadata = dict()
    for key, value in point.items():
        if key.startswith("metadata."):
            metadata[key[9:]] = value
    return metadata


def point_to_sample(point):
    return models.Sample(
        point["source"],
        point["meter"],
        point["type"],
        point["unit"],
        point["value"],
        point["user_id"],
        point["project_id"],
        point["resource_id"],
        utils.sanitize_timestamp(point["timestamp"]),
        transform_metadata(point),
        point["message_id"],
        point["message_signature"],
        utils.sanitize_timestamp(point["recorded_at"])
    )
