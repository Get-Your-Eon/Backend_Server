--
-- PostgreSQL database dump
--

\restrict uh536rP54kyGedDfKStBJ2vTMJ8roBiElGLeQXvenRrJfWW1cYZnacXL1BBSsqe

-- Dumped from database version 18.0 (Postgres.app)
-- Dumped by pg_dump version 18.0 (Postgres.app)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: api_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.api_logs (
    id integer NOT NULL,
    endpoint character varying NOT NULL,
    method character varying NOT NULL,
    api_type character varying(50) NOT NULL,
    status_code integer NOT NULL,
    response_code integer,
    response_msg character varying(255)
);


ALTER TABLE public.api_logs OWNER TO postgres;

--
-- Name: api_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.api_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.api_logs_id_seq OWNER TO postgres;

--
-- Name: api_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.api_logs_id_seq OWNED BY public.api_logs.id;


--
-- Name: chargers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.chargers (
    id integer NOT NULL,
    station_id integer NOT NULL,
    charger_code character varying(50) NOT NULL,
    charger_type character varying(50),
    connector_type character varying(50),
    output_kw double precision,
    status_code integer,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.chargers OWNER TO postgres;

--
-- Name: chargers_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.chargers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.chargers_id_seq OWNER TO postgres;

--
-- Name: chargers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.chargers_id_seq OWNED BY public.chargers.id;


--
-- Name: stations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.stations (
    id integer NOT NULL,
    station_code character varying(50) NOT NULL,
    name character varying(200) NOT NULL,
    address text,
    provider character varying(100),
    location public.geometry(Point,4326),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.stations OWNER TO postgres;

--
-- Name: stations_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.stations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stations_id_seq OWNER TO postgres;

--
-- Name: stations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.stations_id_seq OWNED BY public.stations.id;


--
-- Name: subsidies; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.subsidies (
    id integer NOT NULL,
    manufacturer character varying NOT NULL,
    model_group character varying NOT NULL,
    model_name character varying NOT NULL,
    subsidy_national_10k_won integer NOT NULL,
    subsidy_local_10k_won integer NOT NULL,
    subsidy_total_10k_won integer NOT NULL
);


ALTER TABLE public.subsidies OWNER TO postgres;

--
-- Name: subsidies_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.subsidies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.subsidies_id_seq OWNER TO postgres;

--
-- Name: subsidies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.subsidies_id_seq OWNED BY public.subsidies.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    role character varying(20) NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: api_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_logs ALTER COLUMN id SET DEFAULT nextval('public.api_logs_id_seq'::regclass);


--
-- Name: chargers id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chargers ALTER COLUMN id SET DEFAULT nextval('public.chargers_id_seq'::regclass);


--
-- Name: stations id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stations ALTER COLUMN id SET DEFAULT nextval('public.stations_id_seq'::regclass);


--
-- Name: subsidies id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subsidies ALTER COLUMN id SET DEFAULT nextval('public.subsidies_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alembic_version (version_num) FROM stdin;
82564d70969d
\.


--
-- Data for Name: api_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.api_logs (id, endpoint, method, api_type, status_code, response_code, response_msg) FROM stdin;
\.


--
-- Data for Name: chargers; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.chargers (id, station_id, charger_code, charger_type, connector_type, output_kw, status_code, created_at, updated_at) FROM stdin;
1	1	1	DC Combo	Type 1	50	1	2025-10-06 03:35:45.856677	2025-10-06 03:35:45.856677
2	2	1	DC Combo	Type 1	50	1	2025-10-06 03:35:45.856677	2025-10-06 03:35:45.856677
3	3	1	DC Combo	Type 1	50	1	2025-10-06 03:35:45.856677	2025-10-06 03:35:45.856677
4	4	1	DC Combo	Type 1	50	1	2025-10-06 03:35:45.856677	2025-10-06 03:35:45.856677
5	5	1	DC Combo	Type 1	50	1	2025-10-06 03:35:45.856677	2025-10-06 03:35:45.856677
\.


--
-- Data for Name: spatial_ref_sys; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.spatial_ref_sys (srid, auth_name, auth_srid, srtext, proj4text) FROM stdin;
\.


--
-- Data for Name: stations; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.stations (id, station_code, name, address, provider, location, created_at, updated_at) FROM stdin;
1	ST0001	강남역 충전소	서울 강남구 역삼동 812-1	A사	0101000020E6100000A857CA32C4C15F40D656EC2FBBBF4240	2025-10-06 03:35:45.856677	2025-10-06 03:35:45.856677
2	ST0002	여의도 파크 충전소	서울 영등포구 여의도동 2	B사	0101000020E61000003333333333BB5F402506819543C34240	2025-10-06 03:35:45.856677	2025-10-06 03:35:45.856677
3	ST0003	홍대입구역 충전소	서울 마포구 동교동 167-1	A사	0101000020E6100000DE02098A1FBB5F40107A36AB3EC74240	2025-10-06 03:35:45.856677	2025-10-06 03:35:45.856677
4	ST0004	잠실 롯데 충전소	서울 송파구 올림픽로 300	C사	0101000020E61000001895D40968C65F407D3F355EBAC14240	2025-10-06 03:35:45.856677	2025-10-06 03:35:45.856677
5	ST0005	구로 디지털단지 충전소	서울 구로구 구로동 182-13	B사	0101000020E6100000F7065F984CB95F4012A5BDC117BE4240	2025-10-06 03:35:45.856677	2025-10-06 03:35:45.856677
\.


--
-- Data for Name: subsidies; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.subsidies (id, manufacturer, model_group, model_name, subsidy_national_10k_won, subsidy_local_10k_won, subsidy_total_10k_won) FROM stdin;
1	현대자동차	GV60	GV60 스탠다드 2WD 19인치	287	148	435
2	현대자동차	GV60	GV60 스탠다드 AWD 19인치	261	135	396
3	현대자동차	GV60	GV60 스탠다드 AWD 20인치	251	129	380
4	현대자동차	GV60	GV60 퍼포먼스 AWD 21인치	236	122	358
5	현대자동차	GV70	Electrified GV70 AWD 20인치	244	126	370
6	현대자동차	GV70	Electrified GV70 AWD 19인치	260	134	394
7	현대자동차	아이오닉6	아이오닉6 스탠다드 2WD 18인치	635	272	907
8	현대자동차	아이오닉6	아이오닉6 롱레인지 2WD 18인치	686	297	983
9	현대자동차	아이오닉6	아이오닉6 롱레인지 2WD 20인치	680	294	974
10	현대자동차	아이오닉6	아이오닉6 롱레인지 AWD 18인치	686	297	983
11	현대자동차	아이오닉6	아이오닉6 롱레인지 AWD 20인치	647	277	924
12	현대자동차	코나	코나 일렉트릭 2WD 스탠다드 17인치	573	231	804
13	현대자동차	코나	코나 일렉트릭 2WD 롱레인지 17인치	623	271	894
14	현대자동차	코나	코나 일렉트릭 2WD 롱레인지 19인치(빌트인 캠)	568	242	810
15	현대자동차	아이오닉5	아이오닉5 N	232	120	352
16	현대자동차	아이오닉5	더뉴아이오닉5 2WD 롱레인지 19인치 빌트인 캠 미적용	659	298	957
17	현대자동차	아이오닉5	더뉴아이오닉5 2WD 롱레인지 19인치	656	296	952
18	현대자동차	아이오닉5	더뉴아이오닉5 2WD 롱레인지 20인치	651	294	945
19	현대자동차	아이오닉5	더뉴아이오닉5 AWD 롱레인지 20인치	624	280	904
20	현대자동차	아이오닉5	더뉴아이오닉5 AWD 롱레인지 19인치	650	293	943
21	현대자동차	아이오닉5	더뉴아이오닉5 2WD 롱레인지 N라인 20인치	633	285	918
22	현대자동차	아이오닉5	더뉴아이오닉5 AWD 롱레인지 N라인 20인치	602	268	870
23	현대자동차	G80	Electrified G80 AWD 19인치(2025)	275	142	417
24	현대자동차	아이오닉5	더뉴아이오닉5 2WD 스탠다드 19인치	561	255	816
25	현대자동차	GV70	Electrified GV70 AWD 20인치(2025)	250	129	379
26	현대자동차	GV70	Electrified GV70 AWD 19인치(2025)	266	137	403
27	현대자동차	코나	코나 일렉트릭 2WD 롱레인지 17인치(빌트인 캠)	623	271	894
28	현대자동차	아이오닉9	아이오닉9 성능형 AWD	277	143	420
29	현대자동차	아이오닉9	아이오닉9 항속형 AWD	276	142	418
30	현대자동차	아이오닉9	아이오닉9 항속형 2WD	279	144	423
31	현대자동차	GV60	GV60 퍼포먼스 AWD 21인치(2025)	248	128	376
32	현대자동차	GV60	GV60 스탠다드 AWD 20인치(2025)	266	137	403
33	현대자동차	GV60	GV60 스탠다드 AWD 19인치(2025)	277	143	420
34	현대자동차	GV60	GV60 스탠다드 2WD 19인치(2025)	290	150	440
35	현대자동차	아이오닉6	더 뉴 아이오닉6 2wd 롱레인지 n라인 20인치	580	300	880
36	현대자동차	아이오닉6	더 뉴 아이오닉6 awd 롱레인지 n라인 20인치	547	282	829
37	현대자동차	아이오닉6	더 뉴 아이오닉6 2wd 롱레인지 18인치	580	300	880
38	현대자동차	아이오닉6	더 뉴 아이오닉6 2wd 롱레인지 20인치	580	300	880
39	현대자동차	아이오닉6	더 뉴 아이오닉6 awd 롱레인지 18인치	580	300	880
40	현대자동차	아이오닉6	더 뉴 아이오닉6 awd 롱레인지 20인치	563	291	854
41	현대자동차	아이오닉6	더 뉴 아이오닉6 2wd 스탠다드 18인치	570	294	864
42	기아	Niro EV	The all-new Kia Niro EV	590	258	848
43	기아	EV9	EV9 롱레인지 2WD 19인치	275	142	417
44	기아	EV9	EV9 롱레인지 2WD 20인치	273	141	414
45	기아	EV9	EV9 롱레인지 4WD 19인치	259	133	392
46	기아	EV9	EV9 롱레인지 4WD 21인치	265	137	402
47	기아	EV9	EV9 롱레인지 GTL 4WD 21인치	257	132	389
48	기아	EV6	더뉴EV6 롱레인지 4WD 20인치	617	280	897
49	기아	EV6	더뉴EV6 롱레인지 2WD 20인치	644	294	938
50	기아	EV6	더뉴EV6 롱레인지 4WD 19인치	646	295	941
51	기아	EV6	더뉴EV6 롱레인지 2WD 19인치	655	300	955
52	기아	EV3	EV3 롱레인지 2WD 17인치	565	292	857
53	기아	EV3	EV3 롱레인지 2WD 19인치	565	292	857
54	기아	EV3	EV3 스탠다드 2WD	479	247	726
55	기아	EV6	더뉴EV6 GT	232	120	352
56	기아	EV6	더뉴EV6 스탠다드	582	264	846
57	기아	EV9	EV9 스탠다드	242	125	367
58	기아	EV4	EV4 롱레인지 GTL 2WD 19인치	565	292	857
59	기아	EV4	EV4 스탠다드 2WD 19인치	491	253	744
60	기아	EV4	EV4 롱레인지 2WD 17인치	565	292	857
61	기아	EV4	EV4 롱레인지 2WD 19인치	565	292	857
62	기아	EV4	EV4 스탠다드 2WD 17인치	522	270	792
63	기아	PV5	PV5 패신저 5인승 롱레인지	468	242	710
64	기아	EV5	EV5 롱레인지 2WD	562	290	852
65	르노코리아	scenic	scenic	443	229	672
66	BMW	MINI Cooper	MINI Cooper SE	303	156	459
67	BMW	i4	i4 eDrive40	189	97	286
68	BMW	i4	i4 M50	172	88	260
69	BMW	iX1	iX1 xDrive30	154	79	233
70	BMW	i4	i4 eDrive40 LCI	187	96	283
71	BMW	iX2	iX2 eDrive20	167	86	253
72	BMW	MINI Countryman	MINI Countryman SE ALL4	158	81	239
73	BMW	MINI Countryman	MINI Countryman E	166	85	251
74	BMW	MINI Aceman	MINI Aceman SE	306	158	464
75	BMW	i4	i4 M50 LCI	177	91	268
76	BMW	MINI JCW	MINI JCW Aceman E	151	78	229
77	BMW	MINI JCW	MINI JCW E	147	76	223
78	BMW	MINI Aceman	MINI Aceman E	306	158	464
79	BMW	iX1	ix1 edrive20	166	85	251
80	BMW	i5	i5 edrive 40	198	102	300
81	테슬라코리아	Model 3	(단종)Model 3 RWD(2024)	183	94	277
82	테슬라코리아	Model 3	Model 3 Long Range	202	104	306
83	테슬라코리아	Model Y	(단종)Model Y RWD	201	87	288
84	테슬라코리아	Model Y	(단종)Model Y Long Range	184	95	279
85	테슬라코리아	Model Y	(단종)Model Y Performance	191	98	289
86	테슬라코리아	Model 3	Model 3 Performance	187	96	283
87	테슬라코리아	Model Y	(단종)Model Y Long Range 19인치	202	104	306
88	테슬라코리아	Model 3	Model 3 RWD	186	96	282
89	테슬라코리아	Model Y	New Model Y Long Range	207	107	314
90	테슬라코리아	Model Y	New Model Y RWD	188	97	285
91	메르세데스벤츠코리아	EQB300	(단종)EQB300 4MATIC(Pre-Facelift)(5인승)	152	78	230
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, username, hashed_password, role, created_at, updated_at) FROM stdin;
\.


--
-- Name: api_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.api_logs_id_seq', 1, false);


--
-- Name: chargers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.chargers_id_seq', 5, true);


--
-- Name: stations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.stations_id_seq', 13, true);


--
-- Name: subsidies_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.subsidies_id_seq', 91, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 1, false);


--
-- Name: chargers _station_charger_uc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chargers
    ADD CONSTRAINT _station_charger_uc UNIQUE (station_id, charger_code);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: api_logs api_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_logs
    ADD CONSTRAINT api_logs_pkey PRIMARY KEY (id);


--
-- Name: chargers chargers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chargers
    ADD CONSTRAINT chargers_pkey PRIMARY KEY (id);


--
-- Name: stations stations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stations
    ADD CONSTRAINT stations_pkey PRIMARY KEY (id);


--
-- Name: subsidies subsidies_model_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subsidies
    ADD CONSTRAINT subsidies_model_name_key UNIQUE (model_name);


--
-- Name: subsidies subsidies_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subsidies
    ADD CONSTRAINT subsidies_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_stations_location; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stations_location ON public.stations USING gist (location);


--
-- Name: ix_api_logs_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_api_logs_id ON public.api_logs USING btree (id);


--
-- Name: ix_chargers_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_chargers_id ON public.chargers USING btree (id);


--
-- Name: ix_chargers_station_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_chargers_station_id ON public.chargers USING btree (station_id);


--
-- Name: ix_stations_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_stations_id ON public.stations USING btree (id);


--
-- Name: ix_stations_location; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_stations_location ON public.stations USING btree (location);


--
-- Name: ix_stations_station_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_stations_station_code ON public.stations USING btree (station_code);


--
-- Name: ix_subsidies_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_subsidies_id ON public.subsidies USING btree (id);


--
-- Name: ix_subsidies_manufacturer; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_subsidies_manufacturer ON public.subsidies USING btree (manufacturer);


--
-- Name: ix_subsidies_model_group; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_subsidies_model_group ON public.subsidies USING btree (model_group);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_role; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_users_role ON public.users USING btree (role);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: chargers chargers_station_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chargers
    ADD CONSTRAINT chargers_station_id_fkey FOREIGN KEY (station_id) REFERENCES public.stations(id);


--
-- PostgreSQL database dump complete
--

\unrestrict uh536rP54kyGedDfKStBJ2vTMJ8roBiElGLeQXvenRrJfWW1cYZnacXL1BBSsqe

