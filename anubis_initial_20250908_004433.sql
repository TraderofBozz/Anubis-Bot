--
-- PostgreSQL database dump
--

-- Dumped from database version 16.10
-- Dumped by pg_dump version 16.9 (Ubuntu 16.9-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: anubis; Type: SCHEMA; Schema: -; Owner: doadmin
--

CREATE SCHEMA anubis;


ALTER SCHEMA anubis OWNER TO doadmin;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: anubis; Owner: doadmin
--

CREATE FUNCTION anubis.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION anubis.update_updated_at_column() OWNER TO doadmin;

--
-- Name: update_wallet_stats(); Type: FUNCTION; Schema: anubis; Owner: doadmin
--

CREATE FUNCTION anubis.update_wallet_stats() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Ensure wallet profile exists
    INSERT INTO wallet_profiles (wallet_address, first_seen_at, last_seen_at, last_launch_at)
    VALUES (NEW.creator_wallet, NEW.launch_timestamp, NEW.launch_timestamp, NEW.launch_timestamp)
    ON CONFLICT (wallet_address) DO UPDATE
    SET 
        total_launches = wallet_profiles.total_launches + 1,
        last_launch_at = NEW.launch_timestamp,
        last_seen_at = CURRENT_TIMESTAMP,
        profile_updated_at = CURRENT_TIMESTAMP;
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION anubis.update_wallet_stats() OWNER TO doadmin;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alert_history; Type: TABLE; Schema: anubis; Owner: doadmin
--

CREATE TABLE anubis.alert_history (
    id integer NOT NULL,
    mint_address character varying(44) NOT NULL,
    creator_wallet character varying(44) NOT NULL,
    alert_type character varying(50) NOT NULL,
    alert_tier character varying(20) NOT NULL,
    channel_sent_to character varying(100),
    anubis_score_at_time numeric(5,2),
    developer_tier_at_time character varying(20),
    risk_level_at_time character varying(20),
    message_text text,
    sent_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    delivery_status character varying(20) DEFAULT 'PENDING'::character varying,
    error_message text,
    views integer DEFAULT 0,
    clicks integer DEFAULT 0
);


ALTER TABLE anubis.alert_history OWNER TO doadmin;

--
-- Name: alert_history_id_seq; Type: SEQUENCE; Schema: anubis; Owner: doadmin
--

CREATE SEQUENCE anubis.alert_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE anubis.alert_history_id_seq OWNER TO doadmin;

--
-- Name: alert_history_id_seq; Type: SEQUENCE OWNED BY; Schema: anubis; Owner: doadmin
--

ALTER SEQUENCE anubis.alert_history_id_seq OWNED BY anubis.alert_history.id;


--
-- Name: developer_patterns; Type: TABLE; Schema: anubis; Owner: doadmin
--

CREATE TABLE anubis.developer_patterns (
    wallet_address character varying(44) NOT NULL,
    launch_hours jsonb DEFAULT '{}'::jsonb,
    launch_days jsonb DEFAULT '{}'::jsonb,
    launch_intervals jsonb DEFAULT '[]'::jsonb,
    avg_time_between_launches_minutes numeric(10,2),
    std_dev_launch_interval numeric(10,2),
    launches_per_session integer DEFAULT 0,
    session_duration_minutes numeric(10,2),
    typical_initial_buy_sol numeric(20,9),
    typical_sell_timing_minutes numeric(10,2),
    holds_to_graduation_rate numeric(5,2),
    panic_sell_rate numeric(5,2),
    creates_social_rate numeric(5,2),
    reuses_social_accounts boolean DEFAULT false,
    marketing_spend_estimate_sol numeric(20,9),
    uses_same_rpc boolean DEFAULT false,
    common_rpc_endpoint character varying(255),
    uses_vpn boolean DEFAULT false,
    consistent_gas_settings boolean DEFAULT false,
    analyzed_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    pattern_confidence numeric(5,2) DEFAULT 0
);


ALTER TABLE anubis.developer_patterns OWNER TO doadmin;

--
-- Name: hot_developers; Type: VIEW; Schema: anubis; Owner: doadmin
--

CREATE VIEW anubis.hot_developers AS
SELECT
    NULL::character varying(44) AS wallet_address,
    NULL::numeric(5,2) AS anubis_score,
    NULL::character varying(20) AS developer_tier,
    NULL::character varying(20) AS risk_level,
    NULL::integer AS total_launches,
    NULL::integer AS successful_launches,
    NULL::integer AS failed_launches,
    NULL::integer AS rugged_launches,
    NULL::numeric(5,2) AS success_rate,
    NULL::numeric(5,2) AS rug_rate,
    NULL::numeric(20,4) AS estimated_earnings_sol,
    NULL::numeric(20,2) AS largest_success_mcap,
    NULL::numeric(10,2) AS average_hold_time_hours,
    NULL::numeric(5,2) AS quick_dump_rate,
    NULL::numeric(8,2) AS average_launches_per_day,
    NULL::integer AS peak_launch_hour,
    NULL::integer AS peak_launch_day,
    NULL::jsonb AS preferred_launch_times,
    NULL::numeric(5,2) AS launch_velocity_score,
    NULL::integer AS connected_wallets_count,
    NULL::numeric(5,2) AS network_complexity_score,
    NULL::boolean AS uses_jito,
    NULL::boolean AS uses_mev,
    NULL::timestamp with time zone AS first_seen_at,
    NULL::timestamp with time zone AS last_seen_at,
    NULL::timestamp with time zone AS last_launch_at,
    NULL::timestamp with time zone AS profile_updated_at,
    NULL::integer AS days_active,
    NULL::character varying(50) AS primary_platform,
    NULL::jsonb AS platforms_used,
    NULL::boolean AS is_active,
    NULL::boolean AS is_flagged,
    NULL::text AS flag_reason,
    NULL::character varying(20) AS tracking_priority,
    NULL::text AS notes,
    NULL::jsonb AS tags,
    NULL::bigint AS recent_launches,
    NULL::numeric AS avg_recent_mcap;


ALTER VIEW anubis.hot_developers OWNER TO doadmin;

--
-- Name: metadata_retry_queue; Type: TABLE; Schema: anubis; Owner: doadmin
--

CREATE TABLE anubis.metadata_retry_queue (
    id integer NOT NULL,
    mint_address character varying(44) NOT NULL,
    retry_count integer DEFAULT 0,
    max_retries integer DEFAULT 5,
    last_attempt_at timestamp with time zone,
    next_attempt_at timestamp with time zone,
    error_message text,
    priority character varying(20) DEFAULT 'NORMAL'::character varying,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE anubis.metadata_retry_queue OWNER TO doadmin;

--
-- Name: metadata_retry_queue_id_seq; Type: SEQUENCE; Schema: anubis; Owner: doadmin
--

CREATE SEQUENCE anubis.metadata_retry_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE anubis.metadata_retry_queue_id_seq OWNER TO doadmin;

--
-- Name: metadata_retry_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: anubis; Owner: doadmin
--

ALTER SEQUENCE anubis.metadata_retry_queue_id_seq OWNED BY anubis.metadata_retry_queue.id;


--
-- Name: platform_data; Type: TABLE; Schema: anubis; Owner: doadmin
--

CREATE TABLE anubis.platform_data (
    id integer NOT NULL,
    mint_address character varying(44) NOT NULL,
    platform character varying(50) NOT NULL,
    platform_token_id character varying(255),
    platform_pool_id character varying(255),
    platform_rank integer,
    platform_score numeric(10,2),
    bonding_curve_progress numeric(5,2),
    platform_data jsonb DEFAULT '{}'::jsonb,
    fetched_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE anubis.platform_data OWNER TO doadmin;

--
-- Name: platform_data_id_seq; Type: SEQUENCE; Schema: anubis; Owner: doadmin
--

CREATE SEQUENCE anubis.platform_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE anubis.platform_data_id_seq OWNER TO doadmin;

--
-- Name: platform_data_id_seq; Type: SEQUENCE OWNED BY; Schema: anubis; Owner: doadmin
--

ALTER SEQUENCE anubis.platform_data_id_seq OWNED BY anubis.platform_data.id;


--
-- Name: successful_tokens_archive; Type: TABLE; Schema: anubis; Owner: doadmin
--

CREATE TABLE anubis.successful_tokens_archive (
    mint_address character varying(44) NOT NULL,
    token_name character varying(255) NOT NULL,
    token_symbol character varying(50) NOT NULL,
    creator_wallet character varying(44) NOT NULL,
    peak_market_cap numeric(20,2) NOT NULL,
    peak_reached_at timestamp with time zone,
    time_to_peak_hours numeric(10,2),
    launched_at timestamp with time zone NOT NULL,
    initial_liquidity_sol numeric(20,9),
    graduated_at timestamp with time zone,
    roi_from_launch numeric(10,2),
    sustained_above_100k_hours numeric(10,2),
    developer_profit_sol numeric(20,9),
    developer_sell_pattern jsonb DEFAULT '[]'::jsonb,
    notes text,
    archived_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE anubis.successful_tokens_archive OWNER TO doadmin;

--
-- Name: token_launches; Type: TABLE; Schema: anubis; Owner: doadmin
--

CREATE TABLE anubis.token_launches (
    id integer NOT NULL,
    mint_address character varying(44) NOT NULL,
    token_name character varying(255),
    token_symbol character varying(50),
    token_uri text,
    creator_wallet character varying(44) NOT NULL,
    deployer_wallet character varying(44),
    fee_payer_wallet character varying(44),
    launch_timestamp timestamp with time zone NOT NULL,
    launch_block_slot bigint,
    launch_signature character varying(128),
    platform character varying(50) DEFAULT 'pump.fun'::character varying,
    initial_supply numeric(30,0),
    decimals integer DEFAULT 6,
    initial_liquidity_sol numeric(20,9),
    initial_price numeric(30,18),
    metadata_fetched boolean DEFAULT false,
    metadata_fetch_attempts integer DEFAULT 0,
    metadata_fetch_error text,
    metadata_fetched_at timestamp with time zone,
    is_graduated boolean DEFAULT false,
    graduated_at timestamp with time zone,
    is_rugged boolean DEFAULT false,
    rugged_at timestamp with time zone,
    current_mcap numeric(20,2),
    current_price numeric(30,18),
    peak_mcap numeric(20,2),
    peak_mcap_at timestamp with time zone,
    time_to_peak_minutes integer,
    time_to_100k_minutes integer,
    time_to_1m_minutes integer,
    has_twitter boolean DEFAULT false,
    twitter_handle character varying(100),
    has_telegram boolean DEFAULT false,
    telegram_link character varying(255),
    has_website boolean DEFAULT false,
    website_url character varying(255),
    alert_sent boolean DEFAULT false,
    alert_sent_at timestamp with time zone,
    alert_channel character varying(50),
    alert_tier character varying(20),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE anubis.token_launches OWNER TO doadmin;

--
-- Name: token_launches_id_seq; Type: SEQUENCE; Schema: anubis; Owner: doadmin
--

CREATE SEQUENCE anubis.token_launches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE anubis.token_launches_id_seq OWNER TO doadmin;

--
-- Name: token_launches_id_seq; Type: SEQUENCE OWNED BY; Schema: anubis; Owner: doadmin
--

ALTER SEQUENCE anubis.token_launches_id_seq OWNED BY anubis.token_launches.id;


--
-- Name: token_performance_history; Type: TABLE; Schema: anubis; Owner: doadmin
--

CREATE TABLE anubis.token_performance_history (
    id integer NOT NULL,
    mint_address character varying(44) NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    price numeric(30,18),
    market_cap numeric(20,2),
    volume_24h numeric(20,2),
    liquidity numeric(20,9),
    holder_count integer,
    buy_count_1h integer DEFAULT 0,
    sell_count_1h integer DEFAULT 0,
    unique_buyers_1h integer DEFAULT 0,
    unique_sellers_1h integer DEFAULT 0,
    price_change_1h numeric(10,2),
    volume_change_1h numeric(10,2),
    buy_sell_ratio numeric(5,2)
);


ALTER TABLE anubis.token_performance_history OWNER TO doadmin;

--
-- Name: token_performance_history_id_seq; Type: SEQUENCE; Schema: anubis; Owner: doadmin
--

CREATE SEQUENCE anubis.token_performance_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE anubis.token_performance_history_id_seq OWNER TO doadmin;

--
-- Name: token_performance_history_id_seq; Type: SEQUENCE OWNED BY; Schema: anubis; Owner: doadmin
--

ALTER SEQUENCE anubis.token_performance_history_id_seq OWNED BY anubis.token_performance_history.id;


--
-- Name: wallet_profiles; Type: TABLE; Schema: anubis; Owner: doadmin
--

CREATE TABLE anubis.wallet_profiles (
    wallet_address character varying(44) NOT NULL,
    anubis_score numeric(5,2) DEFAULT 0,
    developer_tier character varying(20),
    risk_level character varying(20),
    total_launches integer DEFAULT 0,
    successful_launches integer DEFAULT 0,
    failed_launches integer DEFAULT 0,
    rugged_launches integer DEFAULT 0,
    success_rate numeric(5,2) DEFAULT 0,
    rug_rate numeric(5,2) DEFAULT 0,
    estimated_earnings_sol numeric(20,4) DEFAULT 0,
    largest_success_mcap numeric(20,2) DEFAULT 0,
    average_hold_time_hours numeric(10,2) DEFAULT 0,
    quick_dump_rate numeric(5,2) DEFAULT 0,
    average_launches_per_day numeric(8,2) DEFAULT 0,
    peak_launch_hour integer,
    peak_launch_day integer,
    preferred_launch_times jsonb DEFAULT '[]'::jsonb,
    launch_velocity_score numeric(5,2) DEFAULT 0,
    connected_wallets_count integer DEFAULT 0,
    network_complexity_score numeric(5,2) DEFAULT 0,
    uses_jito boolean DEFAULT false,
    uses_mev boolean DEFAULT false,
    first_seen_at timestamp with time zone,
    last_seen_at timestamp with time zone,
    last_launch_at timestamp with time zone,
    profile_updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    days_active integer DEFAULT 0,
    primary_platform character varying(50) DEFAULT 'pump.fun'::character varying,
    platforms_used jsonb DEFAULT '[]'::jsonb,
    is_active boolean DEFAULT true,
    is_flagged boolean DEFAULT false,
    flag_reason text,
    tracking_priority character varying(20) DEFAULT 'STANDARD'::character varying,
    notes text,
    tags jsonb DEFAULT '[]'::jsonb,
    CONSTRAINT wallet_profiles_developer_tier_check CHECK (((developer_tier)::text = ANY ((ARRAY['ELITE'::character varying, 'PRO'::character varying, 'AMATEUR'::character varying, 'SCAMMER'::character varying, 'UNKNOWN'::character varying])::text[]))),
    CONSTRAINT wallet_profiles_risk_level_check CHECK (((risk_level)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'EXTREME'::character varying])::text[])))
);


ALTER TABLE anubis.wallet_profiles OWNER TO doadmin;

--
-- Name: token_summary; Type: VIEW; Schema: anubis; Owner: doadmin
--

CREATE VIEW anubis.token_summary AS
 SELECT tl.id,
    tl.mint_address,
    tl.token_name,
    tl.token_symbol,
    tl.token_uri,
    tl.creator_wallet,
    tl.deployer_wallet,
    tl.fee_payer_wallet,
    tl.launch_timestamp,
    tl.launch_block_slot,
    tl.launch_signature,
    tl.platform,
    tl.initial_supply,
    tl.decimals,
    tl.initial_liquidity_sol,
    tl.initial_price,
    tl.metadata_fetched,
    tl.metadata_fetch_attempts,
    tl.metadata_fetch_error,
    tl.metadata_fetched_at,
    tl.is_graduated,
    tl.graduated_at,
    tl.is_rugged,
    tl.rugged_at,
    tl.current_mcap,
    tl.current_price,
    tl.peak_mcap,
    tl.peak_mcap_at,
    tl.time_to_peak_minutes,
    tl.time_to_100k_minutes,
    tl.time_to_1m_minutes,
    tl.has_twitter,
    tl.twitter_handle,
    tl.has_telegram,
    tl.telegram_link,
    tl.has_website,
    tl.website_url,
    tl.alert_sent,
    tl.alert_sent_at,
    tl.alert_channel,
    tl.alert_tier,
    tl.created_at,
    tl.updated_at,
    wp.anubis_score,
    wp.developer_tier,
    wp.risk_level,
    wp.success_rate,
        CASE
            WHEN (tl.current_mcap > (1000000)::numeric) THEN 'MEGA'::text
            WHEN (tl.current_mcap > (100000)::numeric) THEN 'SUCCESS'::text
            WHEN (tl.current_mcap > (10000)::numeric) THEN 'GROWING'::text
            ELSE 'EARLY'::text
        END AS mcap_tier
   FROM (anubis.token_launches tl
     JOIN anubis.wallet_profiles wp ON (((tl.creator_wallet)::text = (wp.wallet_address)::text)))
  ORDER BY tl.launch_timestamp DESC;


ALTER VIEW anubis.token_summary OWNER TO doadmin;

--
-- Name: wallet_relationships; Type: TABLE; Schema: anubis; Owner: doadmin
--

CREATE TABLE anubis.wallet_relationships (
    id integer NOT NULL,
    wallet_a character varying(44) NOT NULL,
    wallet_b character varying(44) NOT NULL,
    relationship_type character varying(50) NOT NULL,
    confidence_score numeric(5,2) DEFAULT 0,
    transaction_count integer DEFAULT 0,
    total_volume_sol numeric(20,9) DEFAULT 0,
    evidence jsonb DEFAULT '{}'::jsonb,
    first_interaction_at timestamp with time zone,
    last_interaction_at timestamp with time zone,
    discovered_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT wallet_relationships_check CHECK (((wallet_a)::text < (wallet_b)::text))
);


ALTER TABLE anubis.wallet_relationships OWNER TO doadmin;

--
-- Name: wallet_relationships_id_seq; Type: SEQUENCE; Schema: anubis; Owner: doadmin
--

CREATE SEQUENCE anubis.wallet_relationships_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE anubis.wallet_relationships_id_seq OWNER TO doadmin;

--
-- Name: wallet_relationships_id_seq; Type: SEQUENCE OWNED BY; Schema: anubis; Owner: doadmin
--

ALTER SEQUENCE anubis.wallet_relationships_id_seq OWNED BY anubis.wallet_relationships.id;


--
-- Name: alert_history id; Type: DEFAULT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.alert_history ALTER COLUMN id SET DEFAULT nextval('anubis.alert_history_id_seq'::regclass);


--
-- Name: metadata_retry_queue id; Type: DEFAULT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.metadata_retry_queue ALTER COLUMN id SET DEFAULT nextval('anubis.metadata_retry_queue_id_seq'::regclass);


--
-- Name: platform_data id; Type: DEFAULT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.platform_data ALTER COLUMN id SET DEFAULT nextval('anubis.platform_data_id_seq'::regclass);


--
-- Name: token_launches id; Type: DEFAULT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.token_launches ALTER COLUMN id SET DEFAULT nextval('anubis.token_launches_id_seq'::regclass);


--
-- Name: token_performance_history id; Type: DEFAULT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.token_performance_history ALTER COLUMN id SET DEFAULT nextval('anubis.token_performance_history_id_seq'::regclass);


--
-- Name: wallet_relationships id; Type: DEFAULT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.wallet_relationships ALTER COLUMN id SET DEFAULT nextval('anubis.wallet_relationships_id_seq'::regclass);


--
-- Data for Name: alert_history; Type: TABLE DATA; Schema: anubis; Owner: doadmin
--

COPY anubis.alert_history (id, mint_address, creator_wallet, alert_type, alert_tier, channel_sent_to, anubis_score_at_time, developer_tier_at_time, risk_level_at_time, message_text, sent_at, delivery_status, error_message, views, clicks) FROM stdin;
\.


--
-- Data for Name: developer_patterns; Type: TABLE DATA; Schema: anubis; Owner: doadmin
--

COPY anubis.developer_patterns (wallet_address, launch_hours, launch_days, launch_intervals, avg_time_between_launches_minutes, std_dev_launch_interval, launches_per_session, session_duration_minutes, typical_initial_buy_sol, typical_sell_timing_minutes, holds_to_graduation_rate, panic_sell_rate, creates_social_rate, reuses_social_accounts, marketing_spend_estimate_sol, uses_same_rpc, common_rpc_endpoint, uses_vpn, consistent_gas_settings, analyzed_at, pattern_confidence) FROM stdin;
\.


--
-- Data for Name: metadata_retry_queue; Type: TABLE DATA; Schema: anubis; Owner: doadmin
--

COPY anubis.metadata_retry_queue (id, mint_address, retry_count, max_retries, last_attempt_at, next_attempt_at, error_message, priority, created_at) FROM stdin;
\.


--
-- Data for Name: platform_data; Type: TABLE DATA; Schema: anubis; Owner: doadmin
--

COPY anubis.platform_data (id, mint_address, platform, platform_token_id, platform_pool_id, platform_rank, platform_score, bonding_curve_progress, platform_data, fetched_at) FROM stdin;
\.


--
-- Data for Name: successful_tokens_archive; Type: TABLE DATA; Schema: anubis; Owner: doadmin
--

COPY anubis.successful_tokens_archive (mint_address, token_name, token_symbol, creator_wallet, peak_market_cap, peak_reached_at, time_to_peak_hours, launched_at, initial_liquidity_sol, graduated_at, roi_from_launch, sustained_above_100k_hours, developer_profit_sol, developer_sell_pattern, notes, archived_at) FROM stdin;
\.


--
-- Data for Name: token_launches; Type: TABLE DATA; Schema: anubis; Owner: doadmin
--

COPY anubis.token_launches (id, mint_address, token_name, token_symbol, token_uri, creator_wallet, deployer_wallet, fee_payer_wallet, launch_timestamp, launch_block_slot, launch_signature, platform, initial_supply, decimals, initial_liquidity_sol, initial_price, metadata_fetched, metadata_fetch_attempts, metadata_fetch_error, metadata_fetched_at, is_graduated, graduated_at, is_rugged, rugged_at, current_mcap, current_price, peak_mcap, peak_mcap_at, time_to_peak_minutes, time_to_100k_minutes, time_to_1m_minutes, has_twitter, twitter_handle, has_telegram, telegram_link, has_website, website_url, alert_sent, alert_sent_at, alert_channel, alert_tier, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: token_performance_history; Type: TABLE DATA; Schema: anubis; Owner: doadmin
--

COPY anubis.token_performance_history (id, mint_address, "timestamp", price, market_cap, volume_24h, liquidity, holder_count, buy_count_1h, sell_count_1h, unique_buyers_1h, unique_sellers_1h, price_change_1h, volume_change_1h, buy_sell_ratio) FROM stdin;
\.


--
-- Data for Name: wallet_profiles; Type: TABLE DATA; Schema: anubis; Owner: doadmin
--

COPY anubis.wallet_profiles (wallet_address, anubis_score, developer_tier, risk_level, total_launches, successful_launches, failed_launches, rugged_launches, success_rate, rug_rate, estimated_earnings_sol, largest_success_mcap, average_hold_time_hours, quick_dump_rate, average_launches_per_day, peak_launch_hour, peak_launch_day, preferred_launch_times, launch_velocity_score, connected_wallets_count, network_complexity_score, uses_jito, uses_mev, first_seen_at, last_seen_at, last_launch_at, profile_updated_at, days_active, primary_platform, platforms_used, is_active, is_flagged, flag_reason, tracking_priority, notes, tags) FROM stdin;
\.


--
-- Data for Name: wallet_relationships; Type: TABLE DATA; Schema: anubis; Owner: doadmin
--

COPY anubis.wallet_relationships (id, wallet_a, wallet_b, relationship_type, confidence_score, transaction_count, total_volume_sol, evidence, first_interaction_at, last_interaction_at, discovered_at, updated_at) FROM stdin;
\.


--
-- Name: alert_history_id_seq; Type: SEQUENCE SET; Schema: anubis; Owner: doadmin
--

SELECT pg_catalog.setval('anubis.alert_history_id_seq', 1, false);


--
-- Name: metadata_retry_queue_id_seq; Type: SEQUENCE SET; Schema: anubis; Owner: doadmin
--

SELECT pg_catalog.setval('anubis.metadata_retry_queue_id_seq', 1, false);


--
-- Name: platform_data_id_seq; Type: SEQUENCE SET; Schema: anubis; Owner: doadmin
--

SELECT pg_catalog.setval('anubis.platform_data_id_seq', 1, false);


--
-- Name: token_launches_id_seq; Type: SEQUENCE SET; Schema: anubis; Owner: doadmin
--

SELECT pg_catalog.setval('anubis.token_launches_id_seq', 1, false);


--
-- Name: token_performance_history_id_seq; Type: SEQUENCE SET; Schema: anubis; Owner: doadmin
--

SELECT pg_catalog.setval('anubis.token_performance_history_id_seq', 1, false);


--
-- Name: wallet_relationships_id_seq; Type: SEQUENCE SET; Schema: anubis; Owner: doadmin
--

SELECT pg_catalog.setval('anubis.wallet_relationships_id_seq', 1, false);


--
-- Name: alert_history alert_history_pkey; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.alert_history
    ADD CONSTRAINT alert_history_pkey PRIMARY KEY (id);


--
-- Name: developer_patterns developer_patterns_pkey; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.developer_patterns
    ADD CONSTRAINT developer_patterns_pkey PRIMARY KEY (wallet_address);


--
-- Name: metadata_retry_queue metadata_retry_queue_pkey; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.metadata_retry_queue
    ADD CONSTRAINT metadata_retry_queue_pkey PRIMARY KEY (id);


--
-- Name: platform_data platform_data_mint_address_platform_key; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.platform_data
    ADD CONSTRAINT platform_data_mint_address_platform_key UNIQUE (mint_address, platform);


--
-- Name: platform_data platform_data_pkey; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.platform_data
    ADD CONSTRAINT platform_data_pkey PRIMARY KEY (id);


--
-- Name: successful_tokens_archive successful_tokens_archive_pkey; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.successful_tokens_archive
    ADD CONSTRAINT successful_tokens_archive_pkey PRIMARY KEY (mint_address);


--
-- Name: token_launches token_launches_mint_address_key; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.token_launches
    ADD CONSTRAINT token_launches_mint_address_key UNIQUE (mint_address);


--
-- Name: token_launches token_launches_pkey; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.token_launches
    ADD CONSTRAINT token_launches_pkey PRIMARY KEY (id);


--
-- Name: token_performance_history token_performance_history_mint_address_timestamp_key; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.token_performance_history
    ADD CONSTRAINT token_performance_history_mint_address_timestamp_key UNIQUE (mint_address, "timestamp");


--
-- Name: token_performance_history token_performance_history_pkey; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.token_performance_history
    ADD CONSTRAINT token_performance_history_pkey PRIMARY KEY (id);


--
-- Name: wallet_profiles wallet_profiles_pkey; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.wallet_profiles
    ADD CONSTRAINT wallet_profiles_pkey PRIMARY KEY (wallet_address);


--
-- Name: wallet_relationships wallet_relationships_pkey; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.wallet_relationships
    ADD CONSTRAINT wallet_relationships_pkey PRIMARY KEY (id);


--
-- Name: wallet_relationships wallet_relationships_wallet_a_wallet_b_relationship_type_key; Type: CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.wallet_relationships
    ADD CONSTRAINT wallet_relationships_wallet_a_wallet_b_relationship_type_key UNIQUE (wallet_a, wallet_b, relationship_type);


--
-- Name: idx_alerts_sent; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_alerts_sent ON anubis.alert_history USING btree (sent_at DESC);


--
-- Name: idx_alerts_tier; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_alerts_tier ON anubis.alert_history USING btree (alert_tier);


--
-- Name: idx_alerts_wallet; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_alerts_wallet ON anubis.alert_history USING btree (creator_wallet);


--
-- Name: idx_performance_mint_time; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_performance_mint_time ON anubis.token_performance_history USING btree (mint_address, "timestamp" DESC);


--
-- Name: idx_performance_time; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_performance_time ON anubis.token_performance_history USING btree ("timestamp" DESC);


--
-- Name: idx_retry_queue_next; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_retry_queue_next ON anubis.metadata_retry_queue USING btree (next_attempt_at) WHERE (retry_count < max_retries);


--
-- Name: idx_token_launches_alert_pending; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_token_launches_alert_pending ON anubis.token_launches USING btree (alert_sent) WHERE (alert_sent = false);


--
-- Name: idx_token_launches_creator; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_token_launches_creator ON anubis.token_launches USING btree (creator_wallet);


--
-- Name: idx_token_launches_graduated; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_token_launches_graduated ON anubis.token_launches USING btree (is_graduated) WHERE (is_graduated = true);


--
-- Name: idx_token_launches_mcap; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_token_launches_mcap ON anubis.token_launches USING btree (current_mcap DESC) WHERE (current_mcap > (0)::numeric);


--
-- Name: idx_token_launches_name_symbol; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_token_launches_name_symbol ON anubis.token_launches USING btree (token_name, token_symbol);


--
-- Name: idx_token_launches_timestamp; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_token_launches_timestamp ON anubis.token_launches USING btree (launch_timestamp DESC);


--
-- Name: idx_wallet_profiles_active; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_wallet_profiles_active ON anubis.wallet_profiles USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_wallet_profiles_last_launch; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_wallet_profiles_last_launch ON anubis.wallet_profiles USING btree (last_launch_at DESC);


--
-- Name: idx_wallet_profiles_score; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_wallet_profiles_score ON anubis.wallet_profiles USING btree (anubis_score DESC);


--
-- Name: idx_wallet_profiles_tier; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_wallet_profiles_tier ON anubis.wallet_profiles USING btree (developer_tier);


--
-- Name: idx_wallet_relationships_type; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_wallet_relationships_type ON anubis.wallet_relationships USING btree (relationship_type);


--
-- Name: idx_wallet_relationships_wallet_a; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_wallet_relationships_wallet_a ON anubis.wallet_relationships USING btree (wallet_a);


--
-- Name: idx_wallet_relationships_wallet_b; Type: INDEX; Schema: anubis; Owner: doadmin
--

CREATE INDEX idx_wallet_relationships_wallet_b ON anubis.wallet_relationships USING btree (wallet_b);


--
-- Name: hot_developers _RETURN; Type: RULE; Schema: anubis; Owner: doadmin
--

CREATE OR REPLACE VIEW anubis.hot_developers AS
 SELECT wp.wallet_address,
    wp.anubis_score,
    wp.developer_tier,
    wp.risk_level,
    wp.total_launches,
    wp.successful_launches,
    wp.failed_launches,
    wp.rugged_launches,
    wp.success_rate,
    wp.rug_rate,
    wp.estimated_earnings_sol,
    wp.largest_success_mcap,
    wp.average_hold_time_hours,
    wp.quick_dump_rate,
    wp.average_launches_per_day,
    wp.peak_launch_hour,
    wp.peak_launch_day,
    wp.preferred_launch_times,
    wp.launch_velocity_score,
    wp.connected_wallets_count,
    wp.network_complexity_score,
    wp.uses_jito,
    wp.uses_mev,
    wp.first_seen_at,
    wp.last_seen_at,
    wp.last_launch_at,
    wp.profile_updated_at,
    wp.days_active,
    wp.primary_platform,
    wp.platforms_used,
    wp.is_active,
    wp.is_flagged,
    wp.flag_reason,
    wp.tracking_priority,
    wp.notes,
    wp.tags,
    count(tl.mint_address) AS recent_launches,
    avg(tl.current_mcap) AS avg_recent_mcap
   FROM (anubis.wallet_profiles wp
     LEFT JOIN anubis.token_launches tl ON ((((wp.wallet_address)::text = (tl.creator_wallet)::text) AND (tl.launch_timestamp > (CURRENT_TIMESTAMP - '24:00:00'::interval)))))
  WHERE (wp.is_active = true)
  GROUP BY wp.wallet_address
 HAVING (count(tl.mint_address) > 0)
  ORDER BY wp.anubis_score DESC;


--
-- Name: token_launches trigger_update_wallet_on_launch; Type: TRIGGER; Schema: anubis; Owner: doadmin
--

CREATE TRIGGER trigger_update_wallet_on_launch AFTER INSERT ON anubis.token_launches FOR EACH ROW EXECUTE FUNCTION anubis.update_wallet_stats();


--
-- Name: token_launches update_token_launches_updated_at; Type: TRIGGER; Schema: anubis; Owner: doadmin
--

CREATE TRIGGER update_token_launches_updated_at BEFORE UPDATE ON anubis.token_launches FOR EACH ROW EXECUTE FUNCTION anubis.update_updated_at_column();


--
-- Name: alert_history alert_history_creator_wallet_fkey; Type: FK CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.alert_history
    ADD CONSTRAINT alert_history_creator_wallet_fkey FOREIGN KEY (creator_wallet) REFERENCES anubis.wallet_profiles(wallet_address);


--
-- Name: alert_history alert_history_mint_address_fkey; Type: FK CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.alert_history
    ADD CONSTRAINT alert_history_mint_address_fkey FOREIGN KEY (mint_address) REFERENCES anubis.token_launches(mint_address);


--
-- Name: developer_patterns developer_patterns_wallet_address_fkey; Type: FK CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.developer_patterns
    ADD CONSTRAINT developer_patterns_wallet_address_fkey FOREIGN KEY (wallet_address) REFERENCES anubis.wallet_profiles(wallet_address) ON DELETE CASCADE;


--
-- Name: metadata_retry_queue metadata_retry_queue_mint_address_fkey; Type: FK CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.metadata_retry_queue
    ADD CONSTRAINT metadata_retry_queue_mint_address_fkey FOREIGN KEY (mint_address) REFERENCES anubis.token_launches(mint_address) ON DELETE CASCADE;


--
-- Name: platform_data platform_data_mint_address_fkey; Type: FK CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.platform_data
    ADD CONSTRAINT platform_data_mint_address_fkey FOREIGN KEY (mint_address) REFERENCES anubis.token_launches(mint_address) ON DELETE CASCADE;


--
-- Name: successful_tokens_archive successful_tokens_archive_mint_address_fkey; Type: FK CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.successful_tokens_archive
    ADD CONSTRAINT successful_tokens_archive_mint_address_fkey FOREIGN KEY (mint_address) REFERENCES anubis.token_launches(mint_address);


--
-- Name: token_launches token_launches_creator_wallet_fkey; Type: FK CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.token_launches
    ADD CONSTRAINT token_launches_creator_wallet_fkey FOREIGN KEY (creator_wallet) REFERENCES anubis.wallet_profiles(wallet_address) ON DELETE CASCADE;


--
-- Name: token_performance_history token_performance_history_mint_address_fkey; Type: FK CONSTRAINT; Schema: anubis; Owner: doadmin
--

ALTER TABLE ONLY anubis.token_performance_history
    ADD CONSTRAINT token_performance_history_mint_address_fkey FOREIGN KEY (mint_address) REFERENCES anubis.token_launches(mint_address) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

