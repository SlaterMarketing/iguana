#!/usr/bin/env python3
"""One campaign for one dated show, with a hard stop.

    scripts/meta-show-campaign.py plan
    scripts/meta-show-campaign.py apply --live

The open mic campaigns run forever and point at /open-mic/, which never goes stale. A guest headliner is the
opposite: one night, one landing page, and an ad that must stop before the doors do. So this uses a LIFETIME
budget with a start and an end, which is what makes Meta pace the spend across the window instead of resetting
a daily figure every midnight and overshooting on the last day.

🚨 `end_time` is deliberate here, and it is the opposite of the rule for the open mic ad sets. On those an
end_time is a trap: 31 of them on this account read ACTIVE with a schedule that expired months ago, so the UI
looks busy while nothing spends. Here the expiry IS the feature, because an ad for Friday's show running on
Saturday is worse than no ad. `status` reads it back so a finished campaign is obvious rather than fossilised.

Reuses the open mic builder for the parts that are hard to get right: the rate-limit backoff, the creative
enhancement opt-outs, and the video upload that waits for Meta to finish processing.
"""

import argparse
import datetime as dt
import importlib.util
import pathlib
import sys

ORIGINAL_ARGV = sys.argv[1:]

ROOT = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('openmic', ROOT / 'meta-openmic-campaigns.py')
openmic = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0], 'plan']          # the module parses argv at import
spec.loader.exec_module(openmic)

CANCUN = dt.timezone(dt.timedelta(hours=-5))

SHOW = {
    'slug': 'privilegio-fredy-el-regio',
    'name': 'Privilegio · Fredy El Regio',
    'link': f'{openmic.SITE}/es/eventos/privilegio-fredy-el-regio/',
    # Doors are 9pm Friday. The ad stops an hour before, because a ticket bought at 8:55 for a 9pm show in a
    # town people drive to is a refund waiting to happen.
    'ends': dt.datetime(2026, 9, 25, 20, 0, tzinfo=CANCUN),
    # Total for the whole run, not per day: Meta paces a lifetime budget across the window.
    'lifetime_budget': 120000,            # centavos: 1,200.00 MXN
    # A named act pulls from further than a Tuesday open mic does. 40km reaches Tulum and Puerto Morelos;
    # Cancún is its own entry because it is 68km away and worth its own radius.
    'geo': {
        'cities': [{'key': openmic.PLAYA, 'radius': 40, 'distance_unit': 'kilometer'},
                   {'key': 1508006, 'radius': 25, 'distance_unit': 'kilometer'}],   # Cancún, checked against the geo search
        'location_types': ['home', 'recent'],
    },
    'videos': ['fredy-9x16-short.mp4', 'fredy-9x16-long.mp4'],
    'image': 'fredy-flyer-4x5.jpg',
    'story_image': 'fredy-flyer-9x16-safe.jpg',
    'copy': {
        'message': ('Fredy El Regio trae Privilegio a Playa del Carmen, el viernes 25 de septiembre.\n\n'
                    'Una sola función, 80 lugares, en Iguana Comedy en el centro. Boletos 300 MXN y los '
                    'compras aquí en menos de un minuto.'),
        'title': 'Fredy El Regio en Playa del Carmen',
        'description': 'Viernes 25 de septiembre · 9:00 pm · Iguana Comedy',
    },
}

CAMPAIGN = f'{SHOW["name"]} · boletos'
ADSET = f'{SHOW["name"]} · Riviera Maya · boletos'


def iso(when):
    return when.strftime('%Y-%m-%dT%H:%M:%S%z')


def targeting():
    return {
        'geo_locations': SHOW['geo'],
        'age_min': 18,
        'age_max': 65,
        'location_types': ['home', 'recent'],
        'flexible_spec': [{'interests': [openmic.STANDUP_INTEREST]}],
        'targeting_automation': {'advantage_audience': 0},
    }


def ensure_campaign(live):
    found = openmic.existing('campaigns', CAMPAIGN)
    spec = {
        'name': CAMPAIGN,
        'objective': 'OUTCOME_SALES',
        'special_ad_categories': [],
        'is_adset_budget_sharing_enabled': False,
        'status': 'ACTIVE' if live else 'PAUSED',
    }
    if found:
        openmic.post(found['id'], name=spec['name'], status=spec['status'])
        print(f'  campaign {found["id"]}  {CAMPAIGN} (updated)')
        return found['id']
    made = openmic.post(f'{openmic.AD_ACCOUNT}/campaigns', **spec)
    openmic.remember('campaigns', {'id': made['id'], 'name': CAMPAIGN})
    print(f'  campaign {made["id"]}  {CAMPAIGN} (created)')
    return made['id']


def ensure_adset(campaign_id, live):
    start = dt.datetime.now(CANCUN) + dt.timedelta(minutes=2)
    spec = {
        'name': ADSET,
        'campaign_id': campaign_id,
        'lifetime_budget': SHOW['lifetime_budget'],
        'start_time': iso(start),
        'end_time': iso(SHOW['ends']),
        'billing_event': 'IMPRESSIONS',
        # Without this Meta refuses the ad set outright, asking for a bid amount it does not need.
        'bid_strategy': 'LOWEST_COST_WITHOUT_CAP',
        'optimization_goal': 'OFFSITE_CONVERSIONS',
        'destination_type': 'WEBSITE',
        'promoted_object': {'pixel_id': openmic.PIXEL_ID, 'custom_event_type': openmic.CONVERSION_EVENT},
        'attribution_spec': [{'event_type': 'CLICK_THROUGH', 'window_days': 1},
                             {'event_type': 'VIEW_THROUGH', 'window_days': 1}],
        'targeting': targeting(),
        'status': 'ACTIVE' if live else 'PAUSED',
    }
    found = openmic.existing('adsets', ADSET)
    if found:
        frozen = {'campaign_id', 'optimization_goal', 'promoted_object', 'destination_type', 'billing_event',
                  'attribution_spec', 'start_time'}
        openmic.post(found['id'], **{k: v for k, v in spec.items() if k not in frozen})
        print(f'  ad set   {found["id"]}  {ADSET} (updated)')
        return found['id']
    made = openmic.post(f'{openmic.AD_ACCOUNT}/adsets', **spec)
    openmic.remember('adsets', {'id': made['id'], 'name': ADSET})
    print(f'  ad set   {made["id"]}  {ADSET} (created)')
    return made['id']


def video_creative(video_id, thumbnail, name):
    cta = {'type': 'BUY_TICKETS', 'value': {'link': SHOW['link']}}
    return {
        'name': name,
        'object_story_spec': {
            'page_id': openmic.PAGE_ID, 'instagram_user_id': openmic.INSTAGRAM_ID,
            'video_data': {'video_id': video_id, 'message': SHOW['copy']['message'],
                           'title': SHOW['copy']['title'], 'link_description': SHOW['copy']['description'],
                           'call_to_action': cta, 'image_url': thumbnail},
        },
        'degrees_of_freedom_spec': {'creative_features_spec':
                                    {f: {'enroll_status': 'OPT_OUT'} for f in openmic.OPT_OUT_FEATURES}},
    }


def flyer_creative(feed_hash, story_hash, name):
    return {
        'name': name,
        'object_story_spec': {'page_id': openmic.PAGE_ID, 'instagram_user_id': openmic.INSTAGRAM_ID},
        'asset_feed_spec': {
            'images': [{'hash': feed_hash, 'adlabels': [{'name': f'{name} feed'}]},
                       {'hash': story_hash, 'adlabels': [{'name': f'{name} story'}]}],
            'bodies': [{'text': SHOW['copy']['message']}],
            'titles': [{'text': SHOW['copy']['title']}],
            'descriptions': [{'text': SHOW['copy']['description']}],
            'link_urls': [{'website_url': SHOW['link']}],
            'call_to_action_types': ['BUY_TICKETS'],
            'ad_formats': ['SINGLE_IMAGE'],
            'asset_customization_rules': [
                {'customization_spec': openmic.STORY_PLACEMENTS, 'image_label': {'name': f'{name} story'},
                 'priority': 1},
                {'customization_spec': {}, 'image_label': {'name': f'{name} feed'}, 'priority': 2},
            ],
        },
        'degrees_of_freedom_spec': {'creative_features_spec':
                                    {f: {'enroll_status': 'OPT_OUT'} for f in openmic.OPT_OUT_FEATURES}},
    }


def cmd_plan(_):
    left = SHOW['ends'] - dt.datetime.now(CANCUN)
    hours = left.total_seconds() / 3600
    print(f'\n{SHOW["name"]} -> {SHOW["link"]}')
    print(f'  {CAMPAIGN:52} OUTCOME_SALES  optimise {openmic.CONVERSION_EVENT} via pixel {openmic.PIXEL_ID}')
    print(f'  budget     {SHOW["lifetime_budget"] / 100:,.2f} MXN for the whole run, paced by Meta')
    print(f'  window     now until {SHOW["ends"]:%a %d %b %H:%M} Cancun  ({hours:.1f} hours left)')
    print(f'  targeting  Playa del Carmen 40km + Cancún 25km, home+recent, 18 to 65, stand-up interest')
    print(f'  creative   {", ".join(SHOW["videos"])}, {SHOW["image"]}')
    print(f'             {SHOW["story_image"]} for Story and Reels')
    if hours <= 0:
        print('\n  the window has already closed; nothing would deliver')


def cmd_apply(args):
    openmic.PATIENT = True
    missing = [f for f in [*SHOW['videos'], SHOW['image'], SHOW['story_image']]
               if not (openmic.CREATIVE_DIR / f).exists()]
    if missing:
        sys.exit(f'creative missing from {openmic.CREATIVE_DIR}: {", ".join(missing)}')
    if SHOW['ends'] <= dt.datetime.now(CANCUN):
        sys.exit('the end time has already passed; nothing would deliver')

    print(f'\n{SHOW["name"]} -> {SHOW["link"]}')
    campaign_id = ensure_campaign(args.live)
    adset_id = ensure_adset(campaign_id, args.live)
    blocked = []

    for index, filename in enumerate(SHOW['videos'], start=1):
        video_id = openmic.upload_video(openmic.CREATIVE_DIR / filename)
        openmic.wait_for_video(video_id)
        creative = video_creative(video_id, openmic.video_thumbnail(video_id), f'{CAMPAIGN} · video {index}')
        openmic.try_ad(blocked, 'es', 'show', adset_id, creative, f'{ADSET} · video {index}', args.live)

    feed = openmic.upload_image(openmic.CREATIVE_DIR / SHOW['image'])
    story = openmic.upload_image(openmic.CREATIVE_DIR / SHOW['story_image'])
    openmic.try_ad(blocked, 'es', 'show', adset_id,
                   flyer_creative(feed, story, f'{CAMPAIGN} · flyer'), f'{ADSET} · flyer', args.live)

    if blocked:
        print(f'\n{len(blocked)} ad(s) could not be created:')
        for name, reason in blocked:
            print(f'  {name}\n    {reason}')
        sys.exit(1)
    print('\nlive' if args.live else '\npaused: re-run with --live to start it')


def cmd_status(_):
    adset = openmic.existing('adsets', ADSET, fields='id,name,status,effective_status')
    if not adset:
        print('not built yet')
        return
    row = openmic.get(adset['id'], fields='name,status,effective_status,lifetime_budget,start_time,end_time,budget_remaining')
    print(f"{row['name']}\n  {row['status']} / {row.get('effective_status')}")
    print(f"  budget {int(row.get('lifetime_budget') or 0) / 100:,.2f} MXN  "
          f"remaining {int(row.get('budget_remaining') or 0) / 100:,.2f}")
    print(f"  {row.get('start_time')} -> {row.get('end_time')}")
    data = openmic.get(f"{adset['id']}/insights", fields='spend,impressions,clicks,ctr,actions').get('data', [])
    for r in data:
        acts = {a['action_type']: a['value'] for a in r.get('actions', [])}
        print(f"  spend {float(r['spend']):.2f}  impressions {r['impressions']}  clicks {r['clicks']}  "
              f"ctr {float(r['ctr']):.2f}%")
        print('  ', {k: v for k, v in acts.items()
                     if k in ('purchase', 'initiate_checkout', 'landing_page_view', 'link_click')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('plan').set_defaults(func=cmd_plan)
    sub.add_parser('status').set_defaults(func=cmd_status)
    apply_cmd = sub.add_parser('apply')
    apply_cmd.add_argument('--live', action='store_true', help='Start it. Without this everything is PAUSED.')
    apply_cmd.set_defaults(func=cmd_apply)
    args = parser.parse_args(sys.argv[1:])
    args.func(args)


if __name__ == '__main__':
    sys.argv = [sys.argv[0]] + ORIGINAL_ARGV
    main()
