import math

def irrigation(area_ha, et0, kc, rain, efficiency, soil=0, cap_litres=None):
    values = [area_ha, et0, kc, rain, efficiency, soil]
    if not all(math.isfinite(x) for x in values) or min(values) < 0 or area_ha <= 0 or not 0 < efficiency <= 1:
        raise ValueError('Invalid area, weather or efficiency')
    etc = kc * et0
    net = max(0, etc - rain - soil)
    gross = net / efficiency
    litres = gross * area_ha * 10000
    applied = litres if cap_litres is None else min(litres, max(0, cap_litres))
    return dict(etc_mm=etc, net_mm=net, gross_mm=gross, requirement_litres=litres, permitted_litres=applied, unmet_litres=litres-applied, soil_assumption_mm=soil)

def tank_outflow(opening, inflows, closing, losses=0):
    result = opening + inflows - closing - losses
    if min(opening, inflows, closing, losses, result) < 0: raise ValueError('Invalid measured balance')
    return result

def budget(demand, inflows=None, opening=0, capacity=None, delivery_limit=None):
    if any(x < 0 or not math.isfinite(x) for x in demand): raise ValueError('Invalid demand')
    if inflows is None:
        return dict(daily_demand_litres=demand, demand_litres=sum(demand), unmet_litres=None, supply_status='unavailable', reason='Verified sector-matched supply inputs missing')
    if len(inflows) != len(demand) or any(x < 0 or not math.isfinite(x) for x in inflows): raise ValueError('Invalid inflows')
    if not math.isfinite(opening) or opening < 0 or any(v is not None and (not math.isfinite(v) or v < 0) for v in [capacity, delivery_limit]):raise ValueError('Invalid storage or delivery limit')
    if capacity is not None and opening > capacity:raise ValueError('Opening storage exceeds capacity')
    stored, days = opening, []
    for need, incoming in zip(demand, inflows):
        available = stored + incoming
        delivered = min(need, available, delivery_limit if delivery_limit is not None else available)
        stored = available - delivered
        overflow = max(0, stored - capacity) if capacity is not None else 0
        if capacity is not None:stored = min(capacity, stored)
        days.append(dict(demand_litres=need, inflow_litres=incoming, delivered_litres=delivered, unmet_litres=need-delivered, closing_litres=stored, overflow_litres=overflow))
    return dict(days=days, demand_litres=sum(demand), unmet_litres=sum(d['unmet_litres'] for d in days), supply_status='scenario')
